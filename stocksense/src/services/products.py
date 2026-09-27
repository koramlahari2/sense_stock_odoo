from firebase_admin import firestore
from src.config import get_firestore_client

COLLECTION = "products"


def list_products(active_only: bool = False):
    db = get_firestore_client()
    q = db.collection(COLLECTION)
    if active_only:
        q = q.where("active", "==", True)
    docs = q.stream()
    items = []
    for d in docs:
        data = d.to_dict()
        data["id"] = d.id
        items.append(data)
    items.sort(key=lambda x: x.get("name", ""))
    return items


def get_product(product_id: str):
    db = get_firestore_client()
    doc = db.collection(COLLECTION).document(product_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def sku_exists(sku: str, exclude_id: str = None) -> bool:
    db = get_firestore_client()
    docs = db.collection(COLLECTION).where("sku", "==", sku).stream()
    for d in docs:
        if d.id != exclude_id:
            return True
    return False


def create_product(name, sku, category, unit, unit_cost, reorder_level):
    if sku_exists(sku):
        raise ValueError(f"SKU '{sku}' already exists. SKU must be unique.")
    if unit_cost < 0 or reorder_level < 0:
        raise ValueError("Unit cost and reorder level must not be negative.")
    db = get_firestore_client()
    ref = db.collection(COLLECTION).document()
    ref.set({
        "name": name,
        "sku": sku,
        "category": category,
        "unit": unit,
        "unitCost": unit_cost,
        "reorderLevel": reorder_level,
        "active": True,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def update_product(product_id, **fields):
    if "sku" in fields and sku_exists(fields["sku"], exclude_id=product_id):
        raise ValueError(f"SKU '{fields['sku']}' already exists. SKU must be unique.")
    db = get_firestore_client()
    fields["updatedAt"] = firestore.SERVER_TIMESTAMP
    db.collection(COLLECTION).document(product_id).update(fields)


def set_active(product_id, active: bool):
    db = get_firestore_client()
    db.collection(COLLECTION).document(product_id).update({
        "active": active,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })
