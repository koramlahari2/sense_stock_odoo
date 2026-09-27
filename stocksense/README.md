# StockSense (Python / Streamlit edition)

A modular inventory management system for BuildPro Industries — built with
**Streamlit + Firebase (Auth + Firestore) + Gemini/Grok AI**, all in Python.

---

## 1. Project structure

```
stocksense/
  app.py                     # Streamlit entry point - auth screens + all pages
  requirements.txt
  .env.example                # placeholders only, safe to commit
  .gitignore
  firestore.rules
  secrets/                    # put your service account JSON here (gitignored)
  src/
    config.py                 # loads env vars, initializes Firebase Admin + Auth
    auth.py                   # signup / login / logout / password reset
    services/
      products.py
      warehouses.py
      locations.py
      stock.py                 # read-only stock views, low-stock calc
      operations.py            # receipts / deliveries / transfers / adjustments / movements
      dashboard.py             # KPI + summary aggregation
    ai/
      assistant.py             # StockSense AI - Gemini/Grok, server-side only
    ui/
      styles.py                # CSS + status badges
    utils/
      seed_data.py             # demo data for BuildPro Industries
```

## 2. Where your keys go (read this before running anything)

| What | Where | Notes |
|---|---|---|
| Firebase web config (apiKey, authDomain, etc.) | `.env` → `FIREBASE_*` vars | From Firebase Console → Project Settings → General → Your apps → Web app |
| Firebase service account (Admin SDK) | `./secrets/firebase-service-account.json`, referenced by `GOOGLE_APPLICATION_CREDENTIALS` in `.env` | Firebase Console → Project Settings → Service Accounts → Generate New Private Key. **This is a full backend credential — never commit it.** |
| Gemini API key | `.env` → `GEMINI_API_KEY` | From Google AI Studio. Read only in `src/config.py`, only used server-side inside `src/ai/assistant.py`. |
| Grok (xAI) API key | `.env` → `XAI_API_KEY`, and set `AI_PROVIDER=grok` | From console.x.ai. Same server-side-only rule applies. |

Copy the template first:
```bash
cp .env.example .env
```
Then fill in your real values in `.env`. **Never** put any of these values directly in `app.py`, any `src/` file, or commit `.env` / the service account JSON to GitHub — both are already in `.gitignore`.

Because this app is a Streamlit server (not a browser SPA), all Python code — including the AI call — runs on the server. The Gemini/Grok key is read once via `os.getenv(...)` in `src/config.py` and never appears in any HTML/JS sent to the browser.

> Note on the Admin SDK vs. `firestore.rules`: the Firebase **Admin SDK** (used here since Streamlit is a Python server) bypasses Firestore Security Rules by design — rules only apply to direct client SDK access. `firestore.rules` is still included as defense-in-depth for the future / in case you add a mobile or JS client, but the actual access control in this app happens in Python (`src/auth.py` roles + your own checks). If you need rules to be the real enforcement boundary, you'd call Firestore from the browser with the client SDK instead of Admin SDK.

## 3. Local setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your real values
mkdir -p secrets                # put firebase-service-account.json here
```

Enable in Firebase Console:
- **Authentication** → Sign-in method → Email/Password → Enable
- **Firestore Database** → Create database (production mode, not test mode)

Deploy the security rules (optional but recommended):
```bash
npm install -g firebase-tools     # one-time, needs Node.js
firebase login
firebase deploy --only firestore:rules
```

## 4. Seed demo data

```bash
python -m src.utils.seed_data
```
This creates the 3 BuildPro Industries warehouses, 8 products, one rack location per warehouse, and realistic starting stock (including two products already below reorder level, for the low-stock demo).

## 5. Run the app

```bash
streamlit run app.py
```
Sign up for an account (role: `inventory_manager` for full access), then log in.

## 6. Firestore data model

```
users/{uid}            { email, fullName, role, createdAt }
products/{id}          { name, sku, category, unit, unitCost, reorderLevel, active, createdAt, updatedAt }
warehouses/{id}         { name, shortCode, address, createdAt }
locations/{id}          { name, shortCode, warehouseId, createdAt }
stock/{productId_warehouseId_locationId}
                        { productId, warehouseId, locationId, onHand, reserved, updatedAt }
receipts/{id}           { reference, supplier, productId, quantity, warehouseId, locationId,
                          scheduleDate, status, createdBy, createdAt, doneAt }
deliveries/{id}         { reference, customer, productId, quantity, warehouseId, locationId,
                          scheduleDate, status, createdBy, createdAt, doneAt }
transfers/{id}          { reference, productId, quantity, fromWarehouseId, fromLocationId,
                          toWarehouseId, toLocationId, date, status, createdBy, createdAt, doneAt }
adjustments/{id}        { reference, productId, warehouseId, locationId, systemQuantity,
                          countedQuantity, difference, reason, status, createdBy, createdAt, doneAt }
movements/{id}          { reference, type, productId, quantity, fromWarehouseId, fromLocationId,
                          toWarehouseId, toLocationId, status, userId, createdAt }
counters/{prefix}       { value }   # used to generate sequential references like WH/IN/0001
```

Stock document IDs are deterministic (`{productId}_{warehouseId}_{locationId}`), which is what
makes the transactional receipt/delivery/transfer/adjustment logic safe and idempotent — see
`src/services/operations.py` for details and comments.

## 7. Core inventory logic (already implemented)

- **Receipt → Done**: stock increases at that warehouse/location.
- **Delivery → Done**: stock decreases; blocked with "Insufficient stock available." if quantity exceeds on-hand.
- **Transfer → Done**: source decreases, destination increases; total company stock unchanged; blocked if source lacks enough stock.
- **Adjustment → Done**: stock set to the counted quantity; difference and reason recorded.
- Every one of the above runs inside a **Firestore transaction** that re-checks status before applying, so double-clicking "Complete" never double-applies the change — and writes one `movements` record for the audit trail.
- Low stock = `total onHand for a product across all locations <= reorderLevel`, computed live, never hard-coded.

## 8. StockSense AI

`src/ai/assistant.py` pulls a structured JSON snapshot of real product/stock/low-stock/today's-movements
data from Firestore, sends it to Gemini (or Grok) with a system prompt that forbids inventing numbers,
and returns the answer in the chat UI on the "StockSense AI" page. Switch providers by changing
`AI_PROVIDER` in `.env` — no code changes needed.

## 9. Hackathon demo flow

1. Sign up / log in.
2. Dashboard shows live KPIs (all zero/blank until you seed or create data).
3. Run `python -m src.utils.seed_data` if you haven't, then refresh — Products/Stock now populated.
4. Go to **Receipts → New receipt**: 100 kg Steel Rod into Main Warehouse. Save, then click **Complete**. Watch Dashboard/Stock update.
5. Go to **Internal Transfers → New transfer**: 50 kg Steel Rod, Main Warehouse → Production Warehouse. Complete it.
6. Go to **Deliveries → New delivery**: 20 kg Steel Rod. Complete it — stock decreases.
7. Go to **Adjustments → New adjustment**: count Steel Rod as 5 kg less (reason: Damaged). Complete it.
8. Open **Move History** — all four operations appear, filterable by type/product/warehouse.
9. Open **StockSense AI**, ask "How much Steel Rod do we have?" — answered from live Firestore totals.

No manual page refresh is needed — every action calls `st.rerun()` after writing to Firestore.

## 10. Deployment

- **Streamlit Community Cloud**: push this repo (without `.env` / `secrets/`), add `FIREBASE_*`,
  `GEMINI_API_KEY`/`XAI_API_KEY`, and `AI_PROVIDER` as **Secrets** in the app settings, and upload
  the service account JSON contents as a secret too (adjust `src/config.py` to read the JSON from
  `st.secrets` instead of a file path if you deploy this way).
- **Any VM/container**: install `requirements.txt`, place `.env` and `secrets/firebase-service-account.json`
  on the server (never in the image/repo), run `streamlit run app.py --server.port 8501`.

## 11. Required Python packages

See `requirements.txt`: `streamlit`, `firebase-admin`, `pyrebase4`, `python-dotenv`,
`google-generativeai`, `openai` (used for Grok's OpenAI-compatible API), `pandas`.
