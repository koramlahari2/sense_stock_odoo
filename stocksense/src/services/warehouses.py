from firebase_admin import firestore
from src.config import get_firestore_client

COLLECTION = "warehouses"


def list_warehouses():
    db = get_firestore_client()
    items = []
    for d in db.collection(COLLECTION).stream():
        data = d.to_dict()
        data["id"] = d.id
        items.append(data)
    items.sort(key=lambda x: x.get("name", ""))
    return items


def get_warehouse(warehouse_id):
    db = get_firestore_client()
    doc = db.collection(COLLECTION).document(warehouse_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


def create_warehouse(name, short_code, address):
    db = get_firestore_client()
    ref = db.collection(COLLECTION).document()
    ref.set({
        "name": name,
        "shortCode": short_code,
        "address": address,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })
    return ref.id


def update_warehouse(warehouse_id, **fields):
    db = get_firestore_client()
    db.collection(COLLECTION).document(warehouse_id).update(fields)
