"""
This file is the heart of StockSense's inventory logic.

Every function that changes stock:
1. Runs inside a Firestore transaction (atomic - all or nothing).
2. Re-checks the document's status INSIDE the transaction before touching stock,
   so double-clicking "Complete" (or two users clicking at once) cannot double-apply
   a stock change. This is what "idempotent" means here.
3. Always writes a matching row into `movements` for the audit trail.
"""
from datetime import datetime, date
from firebase_admin import firestore
from src.config import get_firestore_client
from src.services.stock import _stock_doc_id, get_stock_doc

STATUS_DRAFT = "Draft"
STATUS_WAITING = "Waiting"
STATUS_READY = "Ready"
STATUS_DONE = "Done"
STATUS_CANCELLED = "Cancelled"


def _next_reference(prefix: str) -> str:
    """Sequential, human friendly reference like WH/IN/0001 using a Firestore counter."""
    db = get_firestore_client()
    counter_ref = db.collection("counters").document(prefix.replace("/", "_"))

    @firestore.transactional
    def bump(txn):
        snap = counter_ref.get(transaction=txn)
        current = snap.to_dict().get("value", 0) if snap.exists else 0
        nxt = current + 1
        txn.set(counter_ref, {"value": nxt})
        return nxt

    txn = db.transaction()
    n = bump(txn)
    return f"{prefix}{n:04d}"


# ---------------------------------------------------------------- RECEIPTS --
def create_receipt(supplier, product_id, quantity, warehouse_id, location_id, schedule_date, user_id):
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0.")
    db = get_firestore_client()
    ref = db.collection("receipts").document()
    ref.set({
        "reference": _next_reference("WH/IN/"),
        "supplier": supplier,
        "productId": product_id,
        "quantity": quantity,
        "warehouseId": warehouse_id,
        "locationId": location_id,
        "scheduleDate": schedule_date.isoformat() if isinstance(schedule_date, date) else schedule_date,
        "status": STATUS_WAITING,
        "createdBy": user_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def complete_receipt(receipt_id: str, user_id: str):
    db = get_firestore_client()
    receipt_ref = db.collection("receipts").document(receipt_id)

    @firestore.transactional
    def _run(txn):
        snap = receipt_ref.get(transaction=txn)
        if not snap.exists:
            raise ValueError("Receipt not found.")
        data = snap.to_dict()
        if data["status"] == STATUS_DONE:
            return False  # already applied - idempotent no-op
        if data["status"] == STATUS_CANCELLED:
            raise ValueError("Cannot complete a cancelled receipt.")

        stock_id = _stock_doc_id(data["productId"], data["warehouseId"], data["locationId"])
        stock_ref = db.collection("stock").document(stock_id)
        stock_snap = stock_ref.get(transaction=txn)
        on_hand = stock_snap.to_dict().get("onHand", 0) if stock_snap.exists else 0

        txn.set(stock_ref, {
            "productId": data["productId"],
            "warehouseId": data["warehouseId"],
            "locationId": data["locationId"],
            "onHand": on_hand + data["quantity"],
            "reserved": stock_snap.to_dict().get("reserved", 0) if stock_snap.exists else 0,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
        txn.update(receipt_ref, {"status": STATUS_DONE, "doneAt": firestore.SERVER_TIMESTAMP})

        movement_ref = db.collection("movements").document()
        txn.set(movement_ref, {
            "reference": data["reference"],
            "type": "RECEIPT",
            "productId": data["productId"],
            "quantity": data["quantity"],
            "fromWarehouseId": None,
            "fromLocationId": None,
            "toWarehouseId": data["warehouseId"],
            "toLocationId": data["locationId"],
            "status": STATUS_DONE,
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        return True

    txn = db.transaction()
    return _run(txn)


def list_receipts():
    db = get_firestore_client()
    items = [dict(d.to_dict(), id=d.id) for d in db.collection("receipts").stream()]
    items.sort(key=lambda x: x.get("scheduleDate", ""), reverse=True)
    return items


# -------------------------------------------------------------- DELIVERIES --
def create_delivery(customer, product_id, quantity, warehouse_id, location_id, schedule_date, user_id):
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0.")
    db = get_firestore_client()
    ref = db.collection("deliveries").document()
    ref.set({
        "reference": _next_reference("WH/OUT/"),
        "customer": customer,
        "productId": product_id,
        "quantity": quantity,
        "warehouseId": warehouse_id,
        "locationId": location_id,
        "scheduleDate": schedule_date.isoformat() if isinstance(schedule_date, date) else schedule_date,
        "status": STATUS_WAITING,
        "createdBy": user_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def complete_delivery(delivery_id: str, user_id: str):
    db = get_firestore_client()
    delivery_ref = db.collection("deliveries").document(delivery_id)

    @firestore.transactional
    def _run(txn):
        snap = delivery_ref.get(transaction=txn)
        if not snap.exists:
            raise ValueError("Delivery not found.")
        data = snap.to_dict()
        if data["status"] == STATUS_DONE:
            return False
        if data["status"] == STATUS_CANCELLED:
            raise ValueError("Cannot complete a cancelled delivery.")

        stock_id = _stock_doc_id(data["productId"], data["warehouseId"], data["locationId"])
        stock_ref = db.collection("stock").document(stock_id)
        stock_snap = stock_ref.get(transaction=txn)
        on_hand = stock_snap.to_dict().get("onHand", 0) if stock_snap.exists else 0
        reserved = stock_snap.to_dict().get("reserved", 0) if stock_snap.exists else 0

        if data["quantity"] > on_hand:
            raise ValueError("Insufficient stock available.")

        txn.update(stock_ref, {
            "onHand": on_hand - data["quantity"],
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
        txn.update(delivery_ref, {"status": STATUS_DONE, "doneAt": firestore.SERVER_TIMESTAMP})

        movement_ref = db.collection("movements").document()
        txn.set(movement_ref, {
            "reference": data["reference"],
            "type": "DELIVERY",
            "productId": data["productId"],
            "quantity": data["quantity"],
            "fromWarehouseId": data["warehouseId"],
            "fromLocationId": data["locationId"],
            "toWarehouseId": None,
            "toLocationId": None,
            "status": STATUS_DONE,
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        return True

    txn = db.transaction()
    return _run(txn)


def list_deliveries():
    db = get_firestore_client()
    items = [dict(d.to_dict(), id=d.id) for d in db.collection("deliveries").stream()]
    items.sort(key=lambda x: x.get("scheduleDate", ""), reverse=True)
    return items


# -------------------------------------------------------------- TRANSFERS --
def create_transfer(product_id, quantity, from_wh, from_loc, to_wh, to_loc, xfer_date, user_id):
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0.")
    if from_wh == to_wh and from_loc == to_loc:
        raise ValueError("Source and destination location cannot be the same.")
    db = get_firestore_client()
    ref = db.collection("transfers").document()
    ref.set({
        "reference": _next_reference("WH/INT/"),
        "productId": product_id,
        "quantity": quantity,
        "fromWarehouseId": from_wh,
        "fromLocationId": from_loc,
        "toWarehouseId": to_wh,
        "toLocationId": to_loc,
        "date": xfer_date.isoformat() if isinstance(xfer_date, date) else xfer_date,
        "status": STATUS_WAITING,
        "createdBy": user_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def complete_transfer(transfer_id: str, user_id: str):
    db = get_firestore_client()
    transfer_ref = db.collection("transfers").document(transfer_id)

    @firestore.transactional
    def _run(txn):
        snap = transfer_ref.get(transaction=txn)
        if not snap.exists:
            raise ValueError("Transfer not found.")
        data = snap.to_dict()
        if data["status"] == STATUS_DONE:
            return False
        if data["status"] == STATUS_CANCELLED:
            raise ValueError("Cannot complete a cancelled transfer.")

        src_id = _stock_doc_id(data["productId"], data["fromWarehouseId"], data["fromLocationId"])
        dst_id = _stock_doc_id(data["productId"], data["toWarehouseId"], data["toLocationId"])
        src_ref = db.collection("stock").document(src_id)
        dst_ref = db.collection("stock").document(dst_id)

        src_snap = src_ref.get(transaction=txn)
        dst_snap = dst_ref.get(transaction=txn)
        src_on_hand = src_snap.to_dict().get("onHand", 0) if src_snap.exists else 0
        dst_on_hand = dst_snap.to_dict().get("onHand", 0) if dst_snap.exists else 0
        dst_reserved = dst_snap.to_dict().get("reserved", 0) if dst_snap.exists else 0

        if data["quantity"] > src_on_hand:
            raise ValueError("Insufficient stock at source location for this transfer.")

        txn.update(src_ref, {"onHand": src_on_hand - data["quantity"], "updatedAt": firestore.SERVER_TIMESTAMP})
        txn.set(dst_ref, {
            "productId": data["productId"],
            "warehouseId": data["toWarehouseId"],
            "locationId": data["toLocationId"],
            "onHand": dst_on_hand + data["quantity"],
            "reserved": dst_reserved,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
        txn.update(transfer_ref, {"status": STATUS_DONE, "doneAt": firestore.SERVER_TIMESTAMP})

        movement_ref = db.collection("movements").document()
        txn.set(movement_ref, {
            "reference": data["reference"],
            "type": "TRANSFER",
            "productId": data["productId"],
            "quantity": data["quantity"],
            "fromWarehouseId": data["fromWarehouseId"],
            "fromLocationId": data["fromLocationId"],
            "toWarehouseId": data["toWarehouseId"],
            "toLocationId": data["toLocationId"],
            "status": STATUS_DONE,
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        return True

    txn = db.transaction()
    return _run(txn)


def list_transfers():
    db = get_firestore_client()
    items = [dict(d.to_dict(), id=d.id) for d in db.collection("transfers").stream()]
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items


# ------------------------------------------------------------ ADJUSTMENTS --
def create_adjustment(product_id, warehouse_id, location_id, counted_qty, reason, user_id):
    if counted_qty < 0:
        raise ValueError("Counted quantity cannot be negative.")
    system_qty = get_stock_doc(product_id, warehouse_id, location_id).get("onHand", 0)
    db = get_firestore_client()
    ref = db.collection("adjustments").document()
    ref.set({
        "reference": _next_reference("WH/ADJ/"),
        "productId": product_id,
        "warehouseId": warehouse_id,
        "locationId": location_id,
        "systemQuantity": system_qty,
        "countedQuantity": counted_qty,
        "difference": counted_qty - system_qty,
        "reason": reason,
        "status": STATUS_WAITING,
        "createdBy": user_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def complete_adjustment(adjustment_id: str, user_id: str):
    db = get_firestore_client()
    adj_ref = db.collection("adjustments").document(adjustment_id)

    @firestore.transactional
    def _run(txn):
        snap = adj_ref.get(transaction=txn)
        if not snap.exists:
            raise ValueError("Adjustment not found.")
        data = snap.to_dict()
        if data["status"] == STATUS_DONE:
            return False

        stock_id = _stock_doc_id(data["productId"], data["warehouseId"], data["locationId"])
        stock_ref = db.collection("stock").document(stock_id)
        stock_snap = stock_ref.get(transaction=txn)
        reserved = stock_snap.to_dict().get("reserved", 0) if stock_snap.exists else 0

        txn.set(stock_ref, {
            "productId": data["productId"],
            "warehouseId": data["warehouseId"],
            "locationId": data["locationId"],
            "onHand": data["countedQuantity"],
            "reserved": reserved,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
        txn.update(adj_ref, {"status": STATUS_DONE, "doneAt": firestore.SERVER_TIMESTAMP})

        movement_ref = db.collection("movements").document()
        txn.set(movement_ref, {
            "reference": data["reference"],
            "type": "ADJUSTMENT",
            "productId": data["productId"],
            "quantity": data["difference"],
            "fromWarehouseId": data["warehouseId"] if data["difference"] < 0 else None,
            "fromLocationId": data["locationId"] if data["difference"] < 0 else None,
            "toWarehouseId": data["warehouseId"] if data["difference"] >= 0 else None,
            "toLocationId": data["locationId"] if data["difference"] >= 0 else None,
            "status": STATUS_DONE,
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        return True

    txn = db.transaction()
    return _run(txn)


def list_adjustments():
    db = get_firestore_client()
    items = [dict(d.to_dict(), id=d.id) for d in db.collection("adjustments").stream()]
    items.sort(key=lambda x: x.get("createdAt") or 0, reverse=True)
    return items


# -------------------------------------------------------------- MOVEMENTS --
def list_movements(product_id=None, movement_type=None, warehouse_id=None, status=None):
    db = get_firestore_client()
    items = [dict(d.to_dict(), id=d.id) for d in db.collection("movements").stream()]
    if product_id:
        items = [m for m in items if m.get("productId") == product_id]
    if movement_type:
        items = [m for m in items if m.get("type") == movement_type]
    if warehouse_id:
        items = [m for m in items if m.get("fromWarehouseId") == warehouse_id or m.get("toWarehouseId") == warehouse_id]
    if status:
        items = [m for m in items if m.get("status") == status]
    items.sort(key=lambda x: x.get("createdAt") or datetime.min, reverse=True)
    return items
