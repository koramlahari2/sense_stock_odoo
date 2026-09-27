from src.config import get_firestore_client
from src.services.products import list_products
from src.services.warehouses import list_warehouses
from src.services.locations import list_locations

COLLECTION = "stock"


def _stock_doc_id(product_id, warehouse_id, location_id):
    """Deterministic doc id so a (product, warehouse, location) triple maps to exactly
    one stock document - this is what makes receipt/delivery/transfer updates safe."""
    return f"{product_id}_{warehouse_id}_{location_id}"


def raw_stock_rows():
    db = get_firestore_client()
    rows = []
    for d in db.collection(COLLECTION).stream():
        data = d.to_dict()
        data["id"] = d.id
        rows.append(data)
    return rows


def get_stock_doc(product_id, warehouse_id, location_id):
    db = get_firestore_client()
    doc_id = _stock_doc_id(product_id, warehouse_id, location_id)
    doc = db.collection(COLLECTION).document(doc_id).get()
    if doc.exists:
        return doc.to_dict()
    return {"onHand": 0, "reserved": 0}


def stock_view():
    """Joined, human-readable stock table with free-to-use computed."""
    products = {p["id"]: p for p in list_products()}
    warehouses = {w["id"]: w for w in list_warehouses()}
    locations = {l["id"]: l for l in list_locations()}
    rows = []
    for s in raw_stock_rows():
        p = products.get(s.get("productId"), {})
        w = warehouses.get(s.get("warehouseId"), {})
        l = locations.get(s.get("locationId"), {})
        on_hand = s.get("onHand", 0)
        reserved = s.get("reserved", 0)
        rows.append({
            "Product": p.get("name", "Unknown"),
            "SKU": p.get("sku", ""),
            "Warehouse": w.get("name", "Unknown"),
            "Location": l.get("name", "Unknown"),
            "Unit Cost": p.get("unitCost", 0),
            "On Hand": on_hand,
            "Reserved": reserved,
            "Free to Use": on_hand - reserved,
            "productId": s.get("productId"),
            "warehouseId": s.get("warehouseId"),
        })
    return rows


def total_stock_for_product(product_id):
    return sum(r.get("onHand", 0) for r in raw_stock_rows() if r.get("productId") == product_id)


def stock_by_warehouse_for_product(product_id):
    warehouses = {w["id"]: w for w in list_warehouses()}
    totals = {}
    for r in raw_stock_rows():
        if r.get("productId") == product_id:
            wid = r.get("warehouseId")
            totals[wid] = totals.get(wid, 0) + r.get("onHand", 0)
    return {warehouses.get(wid, {}).get("name", wid): qty for wid, qty in totals.items()}


def low_stock_products():
    """Product is low-stock if total onHand across all locations <= reorderLevel."""
    products = list_products(active_only=True)
    result = []
    for p in products:
        total = total_stock_for_product(p["id"])
        if total <= p.get("reorderLevel", 0):
            result.append({**p, "totalOnHand": total})
    return result
