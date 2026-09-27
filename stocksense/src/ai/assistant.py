"""
StockSense AI.

The AI never invents numbers: we pull real structured data out of Firestore
first, hand it to the model as context, and instruct it to only use that
data. The API key is read from the server environment (src/config.py) and
never touches the browser - Streamlit renders this entirely server-side.
"""
import json
from datetime import datetime, timezone, date
from src.config import GEMINI_MODEL, get_ai_client
from src.services.products import list_products
from src.services.stock import stock_view, low_stock_products, stock_by_warehouse_for_product
from src.services.operations import list_movements

SYSTEM_PROMPT = (
    "You are StockSense AI, an inventory assistant for a warehouse management system. "
    "You will be given a JSON snapshot of the company's real inventory data. "
    "Answer the user's question using ONLY the numbers in that JSON. "
    "Never invent, estimate, or guess a figure that is not derivable from the data. "
    "If the data doesn't contain what's needed to answer, say so plainly. "
    "Keep answers short, concrete, and business-friendly (2-4 sentences)."
)


def _build_context():
    products = list_products(active_only=True)
    stock_rows = stock_view()
    low_stock = low_stock_products()
    today = date.today().isoformat()
    todays_movements = [
        m for m in list_movements()
        if m.get("createdAt") and getattr(m["createdAt"], "date", lambda: None)() and
        m["createdAt"].date().isoformat() == today
    ]

    product_totals = {}
    for row in stock_rows:
        product_totals.setdefault(row["Product"], 0)
        product_totals[row["Product"]] += row["On Hand"]

    context = {
        "products": [{"name": p["name"], "sku": p["sku"], "reorderLevel": p.get("reorderLevel", 0)} for p in products],
        "totalStockByProduct": product_totals,
        "stockByLocation": stock_rows,
        "lowStockProducts": [{"name": p["name"], "totalOnHand": p["totalOnHand"], "reorderLevel": p.get("reorderLevel", 0)} for p in low_stock],
        "todaysMovementsCount": len(todays_movements),
        "todaysMovements": [
            {"type": m.get("type"), "productId": m.get("productId"), "quantity": m.get("quantity")}
            for m in todays_movements
        ],
    }
    return context


def ask(question: str) -> str:
    provider, client = get_ai_client()
    if not provider:
        return (
            "AI is not configured yet. Add GEMINI_API_KEY to your .env file "
            "and set AI_PROVIDER=gemini to enable StockSense AI."
        )

    context = _build_context()
    context_json = json.dumps(context, default=str)
    user_message = f"INVENTORY DATA (JSON):\n{context_json}\n\nQUESTION: {question}"

    try:
        if provider == "gemini":
            model = client.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT,
            )
            response = model.generate_content(user_message)
            return response.text
    except Exception as e:
        return f"AI request failed: {e}"
