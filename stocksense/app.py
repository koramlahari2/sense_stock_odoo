import streamlit as st
import pandas as pd
from datetime import date
from src.auth import sign_up, sign_in, sign_out, send_password_reset, current_user, is_logged_in
from src.ui.styles import CUSTOM_CSS, badge_html
from src.services import products as products_svc
from src.services import warehouses as warehouses_svc
from src.services import locations as locations_svc
from src.services import stock as stock_svc
from src.services import operations as ops_svc
from src.services import dashboard as dashboard_svc
from src.ai import assistant as ai_assistant

st.set_page_config(page_title="StockSense", page_icon="📦", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================== AUTH SCREENS
def render_auth():
    st.markdown('<div class="app-title">📦 StockSense</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Inventory management for BuildPro Industries</div>', unsafe_allow_html=True)
    st.write("")

    tab_login, tab_signup, tab_forgot = st.tabs(["Log in", "Sign up", "Forgot password"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            if not email or not password:
                st.warning("Please enter both email and password.")
            else:
                with st.spinner("Logging in..."):
                    ok, msg = sign_in(email, password)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_signup:
        with st.form("signup_form"):
            full_name = st.text_input("Full name")
            email_s = st.text_input("Email", key="signup_email")
            password_s = st.text_input("Password", type="password", key="signup_pw")
            confirm = st.text_input("Confirm password", type="password")
            role = st.selectbox("Role", ["warehouse_staff", "inventory_manager"])
            submitted_s = st.form_submit_button("Create account", use_container_width=True)
        if submitted_s:
            if not full_name or not email_s or not password_s:
                st.warning("Please fill in all fields.")
            elif password_s != confirm:
                st.error("Passwords do not match.")
            elif len(password_s) < 6:
                st.error("Password should be at least 6 characters.")
            else:
                with st.spinner("Creating account..."):
                    ok, msg = sign_up(email_s, password_s, full_name, role)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    with tab_forgot:
        with st.form("forgot_form"):
            email_f = st.text_input("Email", key="forgot_email")
            submitted_f = st.form_submit_button("Send reset email", use_container_width=True)
        if submitted_f:
            if not email_f:
                st.warning("Please enter your email.")
            else:
                ok, msg = send_password_reset(email_f)
                (st.success if ok else st.error)(msg)


# ================================================================ DASHBOARD
def page_dashboard():
    st.subheader("Dashboard")
    with st.spinner("Loading live inventory data..."):
        kpis = dashboard_svc.get_kpis()

    cols = st.columns(6)
    kpi_defs = [
        ("Total Products", kpis["total_products"]),
        ("Total Stock", kpis["total_stock"]),
        ("Low Stock Items", kpis["low_stock_count"]),
        ("Pending Receipts", kpis["pending_receipts"]),
        ("Pending Deliveries", kpis["pending_deliveries"]),
        ("Internal Transfers", kpis["pending_transfers"]),
    ]
    for col, (label, value) in zip(cols, kpi_defs):
        col.markdown(
            f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")
    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("**Recent inventory movements**")
        movements = dashboard_svc.recent_movements(10)
        if not movements:
            st.info("No movements yet. Complete a receipt, delivery, transfer or adjustment to see activity here.")
        else:
            products_by_id = {p["id"]: p["name"] for p in products_svc.list_products()}
            df = pd.DataFrame([{
                "Reference": m.get("reference"),
                "Type": m.get("type"),
                "Product": products_by_id.get(m.get("productId"), "-"),
                "Qty": m.get("quantity"),
                "Status": m.get("status"),
            } for m in movements])
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("**Warehouse summary**")
        summary = dashboard_svc.warehouse_summary()
        if summary:
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

    with right:
        st.markdown("**Low-stock alert**")
        low_stock = stock_svc.low_stock_products()
        if not low_stock:
            st.success("No products are below their reorder level.")
        else:
            for p in low_stock:
                st.markdown(
                    f"**{p['name']}** ({p['sku']})  \n"
                    f"Stock: {p['totalOnHand']} {p.get('unit','')} • Reorder Level: {p.get('reorderLevel',0)} "
                    + badge_html("Cancelled").replace("Cancelled", "Low Stock"),
                    unsafe_allow_html=True,
                )

        st.markdown("**Pending operations**")
        pending = [r for r in ops_svc.list_receipts() if r["status"] not in ("Done", "Cancelled")]
        pending += [d for d in ops_svc.list_deliveries() if d["status"] not in ("Done", "Cancelled")]
        if not pending:
            st.info("Nothing pending.")
        else:
            for p in pending[:8]:
                st.write(f"• {p['reference']} — {p['status']}")


# ================================================================ PRODUCTS
def page_products():
    st.subheader("Products")
    tab_list, tab_new = st.tabs(["Product list", "New product"])

    with tab_list:
        search = st.text_input("Search by name or SKU", "")
        show_inactive = st.checkbox("Show inactive products", value=False)
        items = products_svc.list_products(active_only=not show_inactive)
        if search:
            s = search.lower()
            items = [p for p in items if s in p["name"].lower() or s in p["sku"].lower()]

        if not items:
            st.info("No products found. Add one in the 'New product' tab.")
        for p in items:
            with st.expander(f"{p['name']} — {p['sku']} {'' if p.get('active', True) else '(inactive)'}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Category:** {p.get('category','-')}")
                c1.write(f"**Unit:** {p.get('unit','-')}")
                c2.write(f"**Unit Cost:** ₹{p.get('unitCost',0)}")
                c2.write(f"**Reorder Level:** {p.get('reorderLevel',0)}")
                total = stock_svc.total_stock_for_product(p["id"])
                st.write(f"**Current total stock:** {total} {p.get('unit','')}")

                with st.form(f"edit_{p['id']}"):
                    name = st.text_input("Name", p["name"], key=f"n_{p['id']}")
                    category = st.text_input("Category", p.get("category", ""), key=f"c_{p['id']}")
                    unit = st.text_input("Unit", p.get("unit", ""), key=f"u_{p['id']}")
                    unit_cost = st.number_input("Unit Cost", value=float(p.get("unitCost", 0)), min_value=0.0, key=f"uc_{p['id']}")
                    reorder = st.number_input("Reorder Level", value=float(p.get("reorderLevel", 0)), min_value=0.0, key=f"r_{p['id']}")
                    save = st.form_submit_button("Save changes")
                if save:
                    try:
                        products_svc.update_product(p["id"], name=name, category=category, unit=unit,
                                                     unitCost=unit_cost, reorderLevel=reorder)
                        st.success("Product updated successfully.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

                toggle_label = "Deactivate" if p.get("active", True) else "Reactivate"
                if st.button(toggle_label, key=f"toggle_{p['id']}"):
                    products_svc.set_active(p["id"], not p.get("active", True))
                    st.rerun()

    with tab_new:
        with st.form("new_product_form"):
            name = st.text_input("Product Name", placeholder="Steel Rod 10mm")
            sku = st.text_input("SKU / Code", placeholder="STL001")
            category = st.text_input("Category", placeholder="Construction")
            unit = st.text_input("Unit of Measure", placeholder="kg")
            unit_cost = st.number_input("Unit Cost", min_value=0.0, step=1.0)
            reorder = st.number_input("Reorder Level", min_value=0.0, step=1.0)
            submitted = st.form_submit_button("Create product", use_container_width=True)
        if submitted:
            if not name or not sku or not unit:
                st.warning("Name, SKU and Unit are required.")
            else:
                try:
                    products_svc.create_product(name, sku, category, unit, unit_cost, reorder)
                    st.success("Product added successfully.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


# ================================================================ STOCK
def page_stock():
    st.subheader("Stock")
    rows = stock_svc.stock_view()
    if not rows:
        st.info("No stock records yet. Complete a receipt to add stock.")
        return

    warehouses = ["All"] + sorted({r["Warehouse"] for r in rows})
    wh_filter = st.selectbox("Filter by warehouse", warehouses)
    if wh_filter != "All":
        rows = [r for r in rows if r["Warehouse"] == wh_filter]

    df = pd.DataFrame(rows)[["Product", "SKU", "Warehouse", "Location", "Unit Cost", "On Hand", "Reserved", "Free to Use"]]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Stock can only change through Receipts, Deliveries, Transfers or Adjustments — never edited directly here.")


# ================================================================ RECEIPTS
def page_receipts(user):
    st.subheader("Receipts (Incoming Goods)")
    tab_list, tab_new = st.tabs(["Receipts", "New receipt"])
    products = products_svc.list_products(active_only=True)
    warehouses = warehouses_svc.list_warehouses()

    with tab_list:
        items = ops_svc.list_receipts()
        if not items:
            st.info("No receipts yet.")
        product_names = {p["id"]: p["name"] for p in products}
        for r in items:
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.write(f"**{r['reference']}** — {product_names.get(r['productId'], '?')}")
            c2.write(f"Supplier: {r.get('supplier','-')} • Qty: {r['quantity']}")
            c3.markdown(badge_html(r["status"]), unsafe_allow_html=True)
            if r["status"] not in ("Done", "Cancelled"):
                if c4.button("Complete", key=f"comp_recv_{r['id']}"):
                    try:
                        applied = ops_svc.complete_receipt(r["id"], user["uid"])
                        st.success("Receipt completed — stock increased." if applied else "Already completed.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    with tab_new:
        if not products or not warehouses:
            st.warning("Add at least one product and warehouse first.")
        else:
            with st.form("new_receipt"):
                supplier = st.text_input("Supplier")
                product = st.selectbox("Product", products, format_func=lambda p: f"{p['name']} ({p['sku']})")
                qty = st.number_input("Quantity", min_value=0.01, step=1.0)
                warehouse = st.selectbox("Warehouse", warehouses, format_func=lambda w: w["name"])
                locs = locations_svc.list_locations(warehouse["id"]) if warehouse else []
                location = st.selectbox("Location", locs, format_func=lambda l: l["name"]) if locs else None
                sched = st.date_input("Schedule date", value=date.today())
                submitted = st.form_submit_button("Save receipt", use_container_width=True)
            if submitted:
                if not location:
                    st.error("This warehouse has no locations yet. Add one under Settings > Locations.")
                elif not supplier:
                    st.warning("Supplier is required.")
                else:
                    ops_svc.create_receipt(supplier, product["id"], qty, warehouse["id"], location["id"], sched, user["uid"])
                    st.success("Receipt created as Waiting. Complete it from the Receipts tab to update stock.")
                    st.rerun()


# ================================================================ DELIVERIES
def page_deliveries(user):
    st.subheader("Deliveries (Outgoing Goods)")
    tab_list, tab_new = st.tabs(["Deliveries", "New delivery"])
    products = products_svc.list_products(active_only=True)
    warehouses = warehouses_svc.list_warehouses()

    with tab_list:
        items = ops_svc.list_deliveries()
        if not items:
            st.info("No deliveries yet.")
        product_names = {p["id"]: p["name"] for p in products}
        for d in items:
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.write(f"**{d['reference']}** — {product_names.get(d['productId'], '?')}")
            c2.write(f"Customer: {d.get('customer','-')} • Qty: {d['quantity']}")
            c3.markdown(badge_html(d["status"]), unsafe_allow_html=True)
            if d["status"] not in ("Done", "Cancelled"):
                if c4.button("Complete", key=f"comp_del_{d['id']}"):
                    try:
                        applied = ops_svc.complete_delivery(d["id"], user["uid"])
                        st.success("Delivery completed — stock decreased." if applied else "Already completed.")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Unable to complete delivery: {e}")

    with tab_new:
        if not products or not warehouses:
            st.warning("Add at least one product and warehouse first.")
        else:
            with st.form("new_delivery"):
                customer = st.text_input("Customer / Contact")
                product = st.selectbox("Product", products, format_func=lambda p: f"{p['name']} ({p['sku']})")
                qty = st.number_input("Quantity", min_value=0.01, step=1.0)
                warehouse = st.selectbox("Warehouse", warehouses, format_func=lambda w: w["name"])
                locs = locations_svc.list_locations(warehouse["id"]) if warehouse else []
                location = st.selectbox("Location", locs, format_func=lambda l: l["name"]) if locs else None
                sched = st.date_input("Schedule date", value=date.today())
                submitted = st.form_submit_button("Save delivery", use_container_width=True)
            if submitted:
                if not location:
                    st.error("This warehouse has no locations yet.")
                elif not customer:
                    st.warning("Customer is required.")
                else:
                    ops_svc.create_delivery(customer, product["id"], qty, warehouse["id"], location["id"], sched, user["uid"])
                    st.success("Delivery created as Waiting. Complete it from the Deliveries tab to update stock.")
                    st.rerun()


# ================================================================ TRANSFERS
def page_transfers(user):
    st.subheader("Internal Transfers")
    tab_list, tab_new = st.tabs(["Transfers", "New transfer"])
    products = products_svc.list_products(active_only=True)
    warehouses = warehouses_svc.list_warehouses()

    with tab_list:
        items = ops_svc.list_transfers()
        if not items:
            st.info("No transfers yet.")
        product_names = {p["id"]: p["name"] for p in products}
        wh_names = {w["id"]: w["name"] for w in warehouses}
        for t in items:
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.write(f"**{t['reference']}** — {product_names.get(t['productId'], '?')}")
            c2.write(f"{wh_names.get(t['fromWarehouseId'],'?')} → {wh_names.get(t['toWarehouseId'],'?')} • Qty: {t['quantity']}")
            c3.markdown(badge_html(t["status"]), unsafe_allow_html=True)
            if t["status"] not in ("Done", "Cancelled"):
                if c4.button("Complete", key=f"comp_xfer_{t['id']}"):
                    try:
                        applied = ops_svc.complete_transfer(t["id"], user["uid"])
                        st.success("Transfer completed." if applied else "Already completed.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    with tab_new:
        if not products or len(warehouses) < 1:
            st.warning("Add at least one product and warehouse first.")
        else:
            with st.form("new_transfer"):
                product = st.selectbox("Product", products, format_func=lambda p: f"{p['name']} ({p['sku']})")
                qty = st.number_input("Quantity", min_value=0.01, step=1.0)
                from_wh = st.selectbox("From warehouse", warehouses, format_func=lambda w: w["name"], key="from_wh")
                from_locs = locations_svc.list_locations(from_wh["id"]) if from_wh else []
                from_loc = st.selectbox("From location", from_locs, format_func=lambda l: l["name"]) if from_locs else None
                to_wh = st.selectbox("To warehouse", warehouses, format_func=lambda w: w["name"], key="to_wh")
                to_locs = locations_svc.list_locations(to_wh["id"]) if to_wh else []
                to_loc = st.selectbox("To location", to_locs, format_func=lambda l: l["name"], key="to_loc_sel") if to_locs else None
                xfer_date = st.date_input("Date", value=date.today())
                submitted = st.form_submit_button("Save transfer", use_container_width=True)
            if submitted:
                if not from_loc or not to_loc:
                    st.error("Both warehouses need at least one location.")
                else:
                    try:
                        ops_svc.create_transfer(product["id"], qty, from_wh["id"], from_loc["id"],
                                                 to_wh["id"], to_loc["id"], xfer_date, user["uid"])
                        st.success("Transfer created as Waiting. Complete it from the Transfers tab.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


# ================================================================ ADJUSTMENTS
def page_adjustments(user):
    st.subheader("Stock Adjustments")
    tab_list, tab_new = st.tabs(["Adjustments", "New adjustment"])
    products = products_svc.list_products(active_only=True)
    warehouses = warehouses_svc.list_warehouses()

    with tab_list:
        items = ops_svc.list_adjustments()
        if not items:
            st.info("No adjustments yet.")
        product_names = {p["id"]: p["name"] for p in products}
        for a in items:
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            c1.write(f"**{a['reference']}** — {product_names.get(a['productId'], '?')}")
            c2.write(f"System: {a['systemQuantity']} → Counted: {a['countedQuantity']} ({a['difference']:+g}) • {a.get('reason','-')}")
            c3.markdown(badge_html(a["status"]), unsafe_allow_html=True)
            if a["status"] not in ("Done", "Cancelled"):
                if c4.button("Complete", key=f"comp_adj_{a['id']}"):
                    applied = ops_svc.complete_adjustment(a["id"], user["uid"])
                    st.success("Adjustment applied." if applied else "Already completed.")
                    st.rerun()

    with tab_new:
        if not products or not warehouses:
            st.warning("Add at least one product and warehouse first.")
        else:
            product = st.selectbox("Product", products, format_func=lambda p: f"{p['name']} ({p['sku']})", key="adj_product")
            warehouse = st.selectbox("Warehouse", warehouses, format_func=lambda w: w["name"], key="adj_wh")
            locs = locations_svc.list_locations(warehouse["id"]) if warehouse else []
            location = st.selectbox("Location", locs, format_func=lambda l: l["name"], key="adj_loc") if locs else None
            if location:
                system_qty = stock_svc.get_stock_doc(product["id"], warehouse["id"], location["id"]).get("onHand", 0)
                st.info(f"Current system quantity: {system_qty}")
            with st.form("new_adjustment"):
                counted = st.number_input("Counted (physical) quantity", min_value=0.0, step=1.0)
                reason = st.selectbox("Reason", ["Damaged", "Lost", "Found", "Counting Error", "Other"])
                submitted = st.form_submit_button("Save adjustment", use_container_width=True)
            if submitted:
                if not location:
                    st.error("This warehouse has no locations yet.")
                else:
                    ops_svc.create_adjustment(product["id"], warehouse["id"], location["id"], counted, reason, user["uid"])
                    st.success("Adjustment created as Waiting. Complete it above to update stock.")
                    st.rerun()


# ================================================================ MOVE HISTORY
def page_move_history():
    st.subheader("Move History")
    products = products_svc.list_products()
    warehouses = warehouses_svc.list_warehouses()
    product_names = {p["id"]: p["name"] for p in products}
    wh_names = {w["id"]: w["name"] for w in warehouses}

    c1, c2, c3 = st.columns(3)
    type_filter = c1.selectbox("Operation type", ["All", "RECEIPT", "DELIVERY", "TRANSFER", "ADJUSTMENT"])
    product_filter = c2.selectbox("Product", ["All"] + [p["name"] for p in products])
    warehouse_filter = c3.selectbox("Warehouse", ["All"] + [w["name"] for w in warehouses])

    product_id = next((p["id"] for p in products if p["name"] == product_filter), None) if product_filter != "All" else None
    warehouse_id = next((w["id"] for w in warehouses if w["name"] == warehouse_filter), None) if warehouse_filter != "All" else None

    movements = ops_svc.list_movements(
        product_id=product_id,
        movement_type=None if type_filter == "All" else type_filter,
        warehouse_id=warehouse_id,
    )

    if not movements:
        st.info("No movements match the current filters.")
        return

    rows = []
    for m in movements:
        from_label = wh_names.get(m.get("fromWarehouseId"), "Vendor" if m["type"] == "RECEIPT" else "-")
        to_label = wh_names.get(m.get("toWarehouseId"), "Customer" if m["type"] == "DELIVERY" else "-")
        rows.append({
            "Reference": m.get("reference"),
            "Type": m.get("type"),
            "Product": product_names.get(m.get("productId"), "?"),
            "Quantity": m.get("quantity"),
            "From": from_label,
            "To": to_label,
            "Status": m.get("status"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ================================================================ WAREHOUSES / LOCATIONS
def page_warehouses():
    st.subheader("Warehouses")
    tab_list, tab_new = st.tabs(["Warehouse list", "New warehouse"])
    with tab_list:
        for w in warehouses_svc.list_warehouses():
            st.write(f"**{w['name']}** ({w['shortCode']}) — {w.get('address','-')}")
    with tab_new:
        with st.form("new_warehouse"):
            name = st.text_input("Name", placeholder="Main Warehouse")
            code = st.text_input("Short code", placeholder="WH01")
            address = st.text_input("Address", placeholder="Hyderabad")
            submitted = st.form_submit_button("Create warehouse", use_container_width=True)
        if submitted:
            if not name or not code:
                st.warning("Name and short code are required.")
            else:
                warehouses_svc.create_warehouse(name, code, address)
                st.success("Warehouse created successfully.")
                st.rerun()


def page_locations():
    st.subheader("Locations")
    warehouses = warehouses_svc.list_warehouses()
    tab_list, tab_new = st.tabs(["Location list", "New location"])
    with tab_list:
        wh_names = {w["id"]: w["name"] for w in warehouses}
        for l in locations_svc.list_locations():
            st.write(f"**{l['name']}** ({l['shortCode']}) — {wh_names.get(l['warehouseId'], '?')}")
    with tab_new:
        if not warehouses:
            st.warning("Create a warehouse first.")
        else:
            with st.form("new_location"):
                warehouse = st.selectbox("Warehouse", warehouses, format_func=lambda w: w["name"])
                name = st.text_input("Location name", placeholder="Rack A")
                code = st.text_input("Short code", placeholder="RA01")
                submitted = st.form_submit_button("Create location", use_container_width=True)
            if submitted:
                if not name or not code:
                    st.warning("Name and short code are required.")
                else:
                    locations_svc.create_location(name, code, warehouse["id"])
                    st.success("Location created successfully.")
                    st.rerun()


# ================================================================ AI
def page_ai():
    st.subheader("StockSense AI")
    st.caption("Ask questions about your real inventory. Answers are grounded in live Firestore data — the AI cannot invent numbers.")

    if "ai_history" not in st.session_state:
        st.session_state["ai_history"] = []

    for role, text in st.session_state["ai_history"]:
        with st.chat_message(role):
            st.write(text)

    question = st.chat_input("e.g. How much Steel Rod do we have?")
    if question:
        st.session_state["ai_history"].append(("user", question))
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Checking inventory data..."):
                answer = ai_assistant.ask(question)
            st.write(answer)
        st.session_state["ai_history"].append(("assistant", answer))


# ================================================================ PROFILE
def page_profile(user):
    st.subheader("Profile")
    st.write(f"**Name:** {user['fullName']}")
    st.write(f"**Email:** {user['email']}")
    st.write(f"**Role:** {user['role']}")


# ================================================================ MAIN
def main():
    if not is_logged_in():
        render_auth()
        return

    user = current_user()

    with st.sidebar:
        st.markdown('<div class="app-title">📦 StockSense</div>', unsafe_allow_html=True)
        st.caption(f"Signed in as {user['fullName']} ({user['role']})")
        st.write("---")

        section = st.radio("Navigate", [
            "Dashboard",
            "Receipts", "Deliveries", "Internal Transfers", "Adjustments",
            "Products", "Stock", "Move History",
            "Warehouses", "Locations",
            "StockSense AI",
            "Profile",
        ], label_visibility="collapsed")

        st.write("---")
        if st.button("Log out", use_container_width=True):
            sign_out()
            st.rerun()

    pages = {
        "Dashboard": page_dashboard,
        "Products": page_products,
        "Stock": page_stock,
        "Receipts": lambda: page_receipts(user),
        "Deliveries": lambda: page_deliveries(user),
        "Internal Transfers": lambda: page_transfers(user),
        "Adjustments": lambda: page_adjustments(user),
        "Move History": page_move_history,
        "Warehouses": page_warehouses,
        "Locations": page_locations,
        "StockSense AI": page_ai,
        "Profile": lambda: page_profile(user),
    }
    pages[section]()


if __name__ == "__main__":
    main()
