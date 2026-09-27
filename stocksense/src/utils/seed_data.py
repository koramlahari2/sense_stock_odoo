"""
Run this once to populate demo data for the hackathon.

    python -m src.utils.seed_data

Safe to re-run: it checks for existing short codes / SKUs before inserting.
"""
from firebase_admin import firestore
from src.config import get_firestore_client
from src.services.warehouses import list_warehouses, create_warehouse
from src.services.locations import list_locations, create_location
from src.services.products import list_products, create_product
from src.services.stock import _stock_doc_id

WAREHOUSES = [
    {"name": "Main Warehouse", "shortCode": "WH01", "address": "Hyderabad"},
    {"name": "Production Warehouse", "shortCode": "WH02", "address": "Warangal"},
    {"name": "Dispatch Warehouse", "shortCode": "WH03", "address": "Vijayawada"},
]

PRODUCTS = [
    {"name": "Steel Rod 10mm", "sku": "STL001", "category": "Construction", "unit": "kg", "unitCost": 3000, "reorderLevel": 100},
    {"name": "Cement 50kg", "sku": "CEM001", "category": "Construction", "unit": "bags", "unitCost": 400, "reorderLevel": 50},
    {"name": "PVC Pipe 2m", "sku": "PVC001", "category": "Plumbing", "unit": "pcs", "unitCost": 250, "reorderLevel": 30},
    {"name": "Electrical Cable", "sku": "CAB001", "category": "Electrical", "unit": "m", "unitCost": 45, "reorderLevel": 200},
    {"name": "Safety Helmet", "sku": "SAF001", "category": "Safety", "unit": "pcs", "unitCost": 300, "reorderLevel": 20},
    {"name": "Welding Rod", "sku": "WEL001", "category": "Tools", "unit": "kg", "unitCost": 180, "reorderLevel": 25},
    {"name": "Wooden Chair", "sku": "CHR001", "category": "Furniture", "unit": "pcs", "unitCost": 1200, "reorderLevel": 15},
    {"name": "Steel Table", "sku": "TAB001", "category": "Furniture", "unit": "pcs", "unitCost": 4500, "reorderLevel": 10},
]

# initial on-hand stock, keyed by product SKU -> warehouse shortCode -> qty
INITIAL_STOCK = {
    "STL001": {"WH01": 500, "WH02": 120},
    "CEM001": {"WH01": 300},
    "PVC001": {"WH01": 80, "WH03": 40},
    "CAB001": {"WH01": 600},
    "SAF001": {"WH01": 15},   # intentionally below reorder level -> low stock demo
    "WEL001": {"WH02": 60},
    "CHR001": {"WH03": 25},
    "TAB001": {"WH03": 8},    # intentionally below reorder level -> low stock demo
}


def seed():
    db = get_firestore_client()

    existing_wh = {w["shortCode"]: w["id"] for w in list_warehouses()}
    for w in WAREHOUSES:
        if w["shortCode"] not in existing_wh:
            wid = create_warehouse(w["name"], w["shortCode"], w["address"])
            existing_wh[w["shortCode"]] = wid
            print(f"Created warehouse {w['name']}")

    existing_loc = {(l["warehouseId"], l["shortCode"]): l["id"] for l in list_locations()}
    default_locations = {}
    for code, wid in existing_wh.items():
        loc_code = f"{code}-A01"
        if (wid, loc_code) not in existing_loc:
            lid = create_location(f"Rack A ({code})", loc_code, wid)
            existing_loc[(wid, loc_code)] = lid
            print(f"Created location {loc_code}")
        default_locations[code] = existing_loc[(wid, loc_code)]

    existing_products = {p["sku"]: p["id"] for p in list_products()}
    for p in PRODUCTS:
        if p["sku"] not in existing_products:
            pid = create_product(p["name"], p["sku"], p["category"], p["unit"], p["unitCost"], p["reorderLevel"])
            existing_products[p["sku"]] = pid
            print(f"Created product {p['name']}")

    for sku, wh_map in INITIAL_STOCK.items():
        pid = existing_products[sku]
        for wh_code, qty in wh_map.items():
            wid = existing_wh[wh_code]
            lid = default_locations[wh_code]
            stock_id = _stock_doc_id(pid, wid, lid)
            db.collection("stock").document(stock_id).set({
                "productId": pid,
                "warehouseId": wid,
                "locationId": lid,
                "onHand": qty,
                "reserved": 0,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }, merge=True)
    print("Seed complete.")


if __name__ == "__main__":
    seed()
