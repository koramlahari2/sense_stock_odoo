from src.services.products import list_products
from src.services.stock import raw_stock_rows, low_stock_products
from src.services.operations import list_receipts, list_deliveries, list_transfers, list_movements
from src.services.warehouses import list_warehouses


def get_kpis():
    products = list_products(active_only=True)
    stock_rows = raw_stock_rows()
    total_stock = sum(r.get("onHand", 0) for r in stock_rows)
    low_stock = low_stock_products()
    pending_receipts = [r for r in list_receipts() if r.get("status") not in ("Done", "Cancelled")]
    pending_deliveries = [d for d in list_deliveries() if d.get("status") not in ("Done", "Cancelled")]
    pending_transfers = [t for t in list_transfers() if t.get("status") not in ("Done", "Cancelled")]

    return {
        "total_products": len(products),
        "total_stock": total_stock,
        "low_stock_count": len(low_stock),
        "pending_receipts": len(pending_receipts),
        "pending_deliveries": len(pending_deliveries),
        "pending_transfers": len(pending_transfers),
    }


def warehouse_summary():
    warehouses = list_warehouses()
    stock_rows = raw_stock_rows()
    summary = []
    for w in warehouses:
        total = sum(r.get("onHand", 0) for r in stock_rows if r.get("warehouseId") == w["id"])
        summary.append({"Warehouse": w["name"], "Code": w.get("shortCode", ""), "Total Stock": total})
    return summary


def recent_movements(limit=10):
    return list_movements()[:limit]
