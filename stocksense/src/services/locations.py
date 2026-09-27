from firebase_admin import firestore
from src.config import get_firestore_client

COLLECTION = "locations"


def list_locations(warehouse_id: str = None):
    db = get_firestore_client()
    q = db.collection(COLLECTION)
    if warehouse_id:
        q = q.where("warehouseId", "==", warehouse_id)
    items = []
    for d in q.stream():
        data = d.to_dict()
        data["id"] = d.id
        items.append(data)
    items.sort(key=lambda x: x.get("name", ""))
    return items


def get_location(location_id):
    db = get_firestore_client()
    doc = db.collection(COLLECTION).document(location_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def create_location(name, short_code, warehouse_id):
    db = get_firestore_client()
    ref = db.collection(COLLECTION).document()
    ref.set({
        "name": name,
        "shortCode": short_code,
        "warehouseId": warehouse_id,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id
