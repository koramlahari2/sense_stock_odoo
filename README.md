# StockSense (Python / Streamlit edition)

A modular inventory management system for BuildPro Industries built with
**Streamlit + Firebase (Auth + Firestore) + Gemini/Grok AI** in Python.

---

## 1. Project structure

```text
stocksense/
  app.py                     # Streamlit entry point: auth + all pages
  requirements.txt
  .env.example               # placeholders only, safe to commit
  .gitignore
  firestore.rules
  secrets/                   # Firebase service account JSON (gitignored)
  src/
    config.py                # loads env vars and initializes Firebase/Admin/Auth
    auth.py                  # signup, login, logout, password reset
    services/
      products.py
      warehouses.py
      locations.py
      stock.py               # stock views and low-stock logic
      operations.py          # receipts, deliveries, transfers, adjustments, movements
      dashboard.py           # KPIs and summary aggregation
    ai/
      assistant.py           # StockSense AI using Gemini/Grok
    ui/
      styles.py              # CSS and status badges
    utils/
      seed_data.py           # demo data for BuildPro Industries
```

---

## 2. Environment and keys

| What | Where | Notes |
|---|---|---|
| Firebase web config (`apiKey`, `authDomain`, etc.) | `.env` → `FIREBASE_*` vars | From Firebase Console → Project Settings → General → Your apps → Web app |
| Firebase service account (Admin SDK) | `./secrets/firebase-service-account.json` via `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Console → Project Settings → Service Accounts → Generate New Private Key. This is a backend credential and should never be committed. |
| Gemini API key | `.env` → `GEMINI_API_KEY` | Provided by Google AI Studio. Used only on the server. |
| Grok API key | `.env` → `XAI_API_KEY` and `AI_PROVIDER=grok` | Provided by xAI. Used only on the server. |

Copy the template first:

```bash
cp .env.example .env
```

Then fill in your real values in `.env`. Never put any secret directly in `app.py` or inside any `src/` file, and never commit `.env` or the service account JSON to GitHub.

Because this app runs as a Streamlit server, the AI call happens on the backend. The Gemini/Grok key is read once via `os.getenv(...)` in `src/config.py` and is not exposed in browser HTML or JavaScript.

> Note: the Firebase Admin SDK bypasses Firestore Security Rules by design. The rules file is still included as defense-in-depth for future client-side access, but the real application access control happens in Python via `src/auth.py` and role checks.

Example `.env`:

```env
FIREBASE_API_KEY=
FIREBASE_AUTH_DOMAIN=
FIREBASE_PROJECT_ID=
FIREBASE_STORAGE_BUCKET=
FIREBASE_MESSAGING_SENDER_ID=
FIREBASE_APP_ID=
FIREBASE_DATABASE_URL=

GOOGLE_APPLICATION_CREDENTIALS=./secrets/firebase-service-account.json

AI_PROVIDER=gemini
GEMINI_MODEL=gemini-3.8-flash
GEMINI_API_KEY=
XAI_API_KEY=
```

---

## 3. Local setup

### 1) Clone the repository

```bash
git clone https://github.com/koramlahari2/sense_stock_odoo.git
cd sense_stock_odoo
```

### 2) Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```cmd
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3) Install dependencies

```bash
python -m pip install -r requirements.txt
```

Main dependencies:

- Streamlit
- Firebase Admin SDK
- Pyrebase4
- Python Dotenv
- Google Generative AI
- OpenAI
- Pandas

### 4) Create the Firebase secret folder

```bash
mkdir -p secrets
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force secrets
```

Place your Firebase service account JSON here:

```text
secrets/firebase-service-account.json
```

---

## 4. Seed demo data

```bash
python -m src.utils.seed_data
```

This creates the BuildPro Industries warehouses, products, rack locations, and realistic starting stock, including products already below reorder level for the low-stock demo.

---

## 5. Run the app

```bash
streamlit run app.py
```

On Windows, this is also valid:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the app in the browser at:

```text
http://localhost:8501
```

Sign up for an account with the `inventory_manager` role for full access, then log in.

---

## 6. Firestore data model

```text
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
counters/{prefix}       { value }   # used to generate references like WH/IN/0001
```

Stock document IDs are deterministic: `{productId}_{warehouseId}_{locationId}`. That allows the receipt, delivery, transfer, and adjustment logic to remain transactional and idempotent.

---

## 7. Core inventory logic

- **Receipt → Done**: stock increases at the target warehouse and location.
- **Delivery → Done**: stock decreases; blocked with "Insufficient stock available." if quantity exceeds on-hand.
- **Transfer → Done**: source decreases, destination increases, and total company stock remains unchanged; blocked when source stock is insufficient.
- **Adjustment → Done**: stock is set to the counted quantity, and the difference/reason is recorded.
- Every operation runs inside a **Firestore transaction** and re-checks status before applying, preventing double-submission from repeated clicks.
- Low stock is computed live as `total onHand for a product across all locations <= reorderLevel` and is not hard-coded.

---

## 8. StockSense AI

`src/ai/assistant.py` pulls a structured JSON snapshot of real product, stock, low-stock, and movement data from Firestore, sends it to Gemini or Grok with a system prompt that forbids invented numbers, and returns a grounded answer in the app UI.

Switch providers by updating `AI_PROVIDER` in `.env`; no code changes are required.

---

## 9. Demo flow

1. Sign up or log in.
2. Open the dashboard and confirm KPIs appear after seeding or creating data.
3. Run `python -m src.utils.seed_data` if you have not already done so.
4. Go to **Receipts → New receipt** and record 100 kg of Steel Rod into the Main Warehouse. Save and click **Complete**.
5. Go to **Internal Transfers → New transfer** and move 50 kg of Steel Rod from Main Warehouse to Production Warehouse.
6. Go to **Deliveries → New delivery** and issue 20 kg of Steel Rod.
7. Go to **Adjustments → New adjustment** and count Steel Rod 5 kg lower with reason `Damaged`.
8. Open **Move History** to review all operations by type, product, and warehouse.
9. Open **StockSense AI** and ask, "How much Steel Rod do we have?" to see live totals from Firestore.

No manual page refresh is required; each action triggers `st.rerun()` after writing to Firestore.

---

## 10. Deployment

- **Streamlit Community Cloud**: push this repo without `.env` and `secrets/`, then add `FIREBASE_*`, `GEMINI_API_KEY`/`XAI_API_KEY`, and `AI_PROVIDER` as app secrets. If needed, upload the JSON service account content as a secret and adjust `src/config.py` to read it from `st.secrets`.
- **Any VM or container**: install dependencies from `requirements.txt`, place `.env` and `secrets/firebase-service-account.json` on the server, and run:

```bash
streamlit run app.py --server.port 8501
```

---

## 11. Firebase Firestore rules

Firebase CLI is required if you want to deploy Firestore security rules.

Install Firebase CLI:

```bash
npm install -g firebase-tools
```

Log in:

```bash
firebase login
```

Deploy rules:

```bash
firebase deploy --only firestore:rules
```

---

## 12. Security and required files

The following files and folders contain sensitive local information and should not be committed:

```text
.env
.venv/
secrets/
secrets/firebase-service-account.json
```

The repository should include:

```text
.env.example
requirements.txt
.gitignore
README.md
```

---

## 13. Troubleshooting

### Firebase Admin module not found

If you see the error:

```text
ModuleNotFoundError: No module named 'firebase_admin'
```

Activate the environment and install the missing dependency:

```bash
python -m pip install firebase-admin
```

Then verify installation:

```bash
python -c "import firebase_admin; print(firebase_admin.__version__)"
```

### Check installed dependencies

```bash
python -m pip list
```

### Common notes

- Do not upload `.venv`, `.env`, or Firebase credentials to GitHub.
- Do not expose Gemini, OpenAI, or other API keys publicly.
- Use `.env.example` to document required variables.
- Use `requirements.txt` to reproduce the Python environment.

---

## 14. Required Python packages

```text
streamlit>=1.38
firebase-admin>=6.5
pyrebase4>=4.7
python-dotenv>=1.0
google-generativeai>=0.7
openai>=1.40
pandas>=2.2
```

Install them with:

```bash
python -m pip install -r requirements.txt
```
