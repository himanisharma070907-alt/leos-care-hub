import streamlit as st
import pandas as pd
import sqlite3
import hmac
from datetime import date, datetime
from zoneinfo import ZoneInfo

# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="Leo's Care Hub 🐾",
    page_icon="🐶",
    layout="wide"
)

# ---------------- PASSWORD PROTECTION ----------------
# Set APP_PASSWORD in Streamlit Community Cloud > App settings > Secrets.
# Never write the real password directly in this file.

try:
    APP_PASSWORD = str(st.secrets["APP_PASSWORD"])
except Exception:
    st.error(
        "App password is not configured. The app owner must add "
        "APP_PASSWORD in Streamlit App settings > Secrets."
    )
    st.stop()

if not st.session_state.get("authenticated", False):
    st.title("🐾 Leo's Care Hub")
    st.subheader("Private access")
    st.write("Enter the password to open Leo's Care Hub.")

    with st.form("login_form"):
        entered_password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your private password"
        )
        login_clicked = st.form_submit_button("Log in")

    if login_clicked:
        if hmac.compare_digest(entered_password, APP_PASSWORD):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")

    st.stop()

# A logout button is shown only after successful login.
if st.sidebar.button("Log out"):
    st.session_state["authenticated"] = False
    st.rerun()

DB = "leo_care.db"

# ---------------- DATABASE ----------------

def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    conn = connect()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        item TEXT PRIMARY KEY,
        quantity REAL DEFAULT 0,
        unit TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS care (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        name TEXT,
        last_date TEXT,
        next_date TEXT,
        notes TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS essentials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT,
        quantity TEXT,
        purchased INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS usage_log (
        item TEXT,
        usage_date TEXT,
        PRIMARY KEY (item, usage_date)
    )
    """)

    c.execute("""
    INSERT OR IGNORE INTO inventory VALUES
    ('Biscuits', 0, 'pieces'),
    ('Chicken Gravy', 0, 'packets')
    """)

    c.execute("""
    INSERT OR IGNORE INTO settings VALUES
    ('daily_biscuits', 9),
    ('daily_gravy', 1)
    """)

    conn.commit()
    conn.close()

setup_database()

# ---------------- DAILY STOCK DEDUCTION ----------------

def deduct_daily_stock():
    today = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).date().isoformat()

    conn = connect()
    c = conn.cursor()

    settings = dict(
        c.execute("SELECT key, value FROM settings").fetchall()
    )

    usage = {
        "Biscuits": settings["daily_biscuits"],
        "Chicken Gravy": settings["daily_gravy"]
    }

    for item, amount in usage.items():

        already_done = c.execute("""
            SELECT 1 FROM usage_log
            WHERE item=? AND usage_date=?
        """, (item, today)).fetchone()

        if not already_done:

            stock = c.execute("""
                SELECT quantity FROM inventory WHERE item=?
            """, (item,)).fetchone()

            if stock and stock["quantity"] >= amount:
                c.execute("""
                    UPDATE inventory
                    SET quantity = quantity - ?
                    WHERE item=?
                """, (amount, item))

            c.execute("""
                INSERT INTO usage_log VALUES (?, ?)
            """, (item, today))

    conn.commit()
    conn.close()

# Run only once per item per day when the website is opened
deduct_daily_stock()

# ---------------- DESIGN ----------------

st.markdown("""
<style>
.stApp {
    background-color: #FFF9F0;
}
h1, h2, h3 {
    color: #8B5E3C;
}
.stButton button {
    background-color: #D9A679;
    color: white;
    border-radius: 12px;
    border: none;
}
[data-testid="stMetric"] {
    background-color: #F7EBDD;
    padding: 15px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------

st.title("🐾 Leo's Care Hub")
st.caption("A happy life starts with good care ❤️")

st.markdown("""
### Welcome to Leo's little corner!
**Labrador Retriever | 5 Years Old**
""")

# ---------------- NAVIGATION ----------------

pages = [
    "🏠 Dashboard",
    "💉 Health Records",
    "🍖 Food Inventory",
    "🛍️ Essentials",
    "🛁 Bath Schedule"
]

page = st.sidebar.radio("Navigate", pages)

# ---------------- DASHBOARD ----------------

if page == "🏠 Dashboard":

    st.header("Leo's Dashboard")

    conn = connect()

    stock = pd.read_sql_query(
        "SELECT * FROM inventory", conn
    )

    settings = dict(
        conn.execute(
            "SELECT key, value FROM settings"
        ).fetchall()
    )

    care = pd.read_sql_query(
        "SELECT * FROM care ORDER BY next_date", conn
    )

    conn.close()

    col1, col2, col3 = st.columns(3)

    col1.metric("🐶 Age", "5 Years")
    col2.metric("🦴 Biscuits", f"{stock.iloc[0]['quantity']:g} pieces")
    col3.metric("🍗 Chicken Gravy", f"{stock.iloc[1]['quantity']:g} packets")

    st.subheader("📅 Upcoming Care")

    if not care.empty:
        care["next_date"] = pd.to_datetime(care["next_date"]).dt.date
        today = date.today()
        upcoming = care[care["next_date"] >= today].head(5)

        if not upcoming.empty:
            st.dataframe(
                upcoming[["category", "name", "next_date"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No upcoming care reminders.")
    else:
        st.info("Add Leo's vaccination, deworming and bath dates.")

    st.subheader("⚠️ Stock Alerts")

    for _, item in stock.iterrows():
        threshold = 10 if item["item"] == "Biscuits" else 3
        if item["quantity"] <= threshold:
            st.warning(f"{item['item']} stock is low! Restock soon.")

    st.subheader("⚙️ Daily Consumption Settings")

    with st.form("daily_settings"):
        biscuits = st.number_input(
            "Biscuits per day",
            min_value=0.0,
            value=float(settings["daily_biscuits"])
        )

        gravy = st.number_input(
            "Chicken gravy packets per day",
            min_value=0.0,
            value=float(settings["daily_gravy"])
        )

        if st.form_submit_button("Save Consumption"):
            conn = connect()
            conn.execute(
                "UPDATE settings SET value=? WHERE key='daily_biscuits'",
                (biscuits,)
            )
            conn.execute(
                "UPDATE settings SET value=? WHERE key='daily_gravy'",
                (gravy,)
            )
            conn.commit()
            conn.close()
            st.success("Daily consumption updated!")
            st.rerun()

# ---------------- HEALTH RECORDS ----------------

elif page == "💉 Health Records":

    st.header("💉 Leo's Health Records")

    with st.form("care_form"):
        category = st.selectbox(
            "Type",
            ["Vaccination", "Deworming", "Bath"]
        )

        name = st.text_input(
            "Vaccine / medicine / activity name",
            placeholder="e.g. Annual vaccination"
        )

        last_date = st.date_input("Date completed")
        next_date = st.date_input("Next due date")
        notes = st.text_area("Notes")

        if st.form_submit_button("Save Record"):
            if name.strip():
                conn = connect()
                conn.execute("""
                    INSERT INTO care
                    (category, name, last_date, next_date, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    category,
                    name,
                    last_date.isoformat(),
                    next_date.isoformat(),
                    notes
                ))
                conn.commit()
                conn.close()
                st.success("Record saved!")
                st.rerun()
            else:
                st.error("Please enter a name.")

    st.divider()
    st.subheader("All Health & Care Records")

    conn = connect()
    records = pd.read_sql_query(
        "SELECT * FROM care ORDER BY next_date",
        conn
    )
    conn.close()

    if not records.empty:
        st.dataframe(
            records.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True
        )

        record_id = st.selectbox(
            "Select a record to delete",
            records["id"].tolist()
        )

        if st.button("Delete Selected Record"):
            conn = connect()
            conn.execute(
                "DELETE FROM care WHERE id=?",
                (record_id,)
            )
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.info("No records added yet.")

# ---------------- FOOD INVENTORY ----------------

elif page == "🍖 Food Inventory":

    st.header("🍖 Leo's Food Inventory")

    conn = connect()
    stock = pd.read_sql_query(
        "SELECT * FROM inventory", conn
    )
    conn.close()

    for _, item in stock.iterrows():
        st.metric(
            item["item"],
            f"{item['quantity']:g} {item['unit']}"
        )

    st.subheader("➕ Restock Food")

    with st.form("restock"):
        item = st.selectbox(
            "Select food",
            ["Biscuits", "Chicken Gravy"]
        )

        quantity = st.number_input(
            "Quantity purchased",
            min_value=0.0,
            value=1.0
        )

        if st.form_submit_button("Add to Stock"):
            if quantity > 0:
                conn = connect()
                conn.execute("""
                    UPDATE inventory
                    SET quantity = quantity + ?
                    WHERE item = ?
                """, (quantity, item))
                conn.commit()
                conn.close()
                st.success("Stock updated successfully!")
                st.rerun()

    st.subheader("📊 Daily Consumption")

    conn = connect()
    settings = dict(
        conn.execute(
            "SELECT key, value FROM settings"
        ).fetchall()
    )
    conn.close()

    st.write(
        f"🦴 Biscuits: {settings['daily_biscuits']:g} pieces/day"
    )
    st.write(
        f"🍗 Chicken gravy: {settings['daily_gravy']:g} packets/day"
    )

    st.caption(
        "Stock is deducted once per item per calendar day "
        "when the website is opened."
    )

# ---------------- ESSENTIALS ----------------

elif page == "🛍️ Essentials":

    st.header("🛍️ Leo's Essentials Shopping List")

    with st.form("essentials_form"):
        item = st.text_input(
            "Essential item",
            placeholder="e.g. Shampoo, leash, dog food"
        )

        quantity = st.text_input(
            "Quantity",
            placeholder="e.g. 1 bottle"
        )

        if st.form_submit_button("Add to List"):
            if item.strip():
                conn = connect()
                conn.execute("""
                    INSERT INTO essentials (item, quantity)
                    VALUES (?, ?)
                """, (item, quantity))
                conn.commit()
                conn.close()
                st.success("Added to shopping list!")
                st.rerun()

    conn = connect()
    items = pd.read_sql_query(
        "SELECT * FROM essentials ORDER BY purchased, id",
        conn
    )
    conn.close()

    st.subheader("Your Shopping List")

    if not items.empty:
        st.dataframe(
            items.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True
        )

        pending = items[items["purchased"] == 0]

        if not pending.empty:
            selected = st.selectbox(
                "Select purchased item",
                pending["id"].tolist(),
                format_func=lambda x: pending.loc[
                    pending["id"] == x, "item"
                ].iloc[0]
            )

            if st.button("Mark as Purchased ✓"):
                conn = connect()
                conn.execute(
                    "UPDATE essentials SET purchased=1 WHERE id=?",
                    (selected,)
                )
                conn.commit()
                conn.close()
                st.rerun()

        if st.button("Clear Purchased Items"):
            conn = connect()
            conn.execute(
                "DELETE FROM essentials WHERE purchased=1"
            )
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.info("Your shopping list is empty.")

# ---------------- BATH SCHEDULE ----------------

elif page == "🛁 Bath Schedule":

    st.header("🛁 Leo's Grooming Diary")

    st.write("Keep track of Leo's baths and grooming appointments.")

    with st.form("bath_form"):
        last_bath = st.date_input(
            "Last bath date",
            value=date.today()
        )

        next_bath = st.date_input(
            "Next bath date"
        )

        notes = st.text_area(
            "Bath / grooming notes"
        )

        if st.form_submit_button("Save Bath Schedule"):
            conn = connect()
            conn.execute("""
                INSERT INTO care
                (category, name, last_date, next_date, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "Bath",
                "Regular Bath",
                last_bath.isoformat(),
                next_bath.isoformat(),
                notes
            ))
            conn.commit()
            conn.close()
            st.success("Bath schedule saved!")
            st.rerun()

    conn = connect()
    baths = pd.read_sql_query(
        "SELECT * FROM care WHERE category='Bath' ORDER BY next_date",
        conn
    )
    conn.close()

    st.subheader("Bath History")

    if not baths.empty:
        st.dataframe(
            baths.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No bath records yet.")

# ---------------- FOOTER ----------------

st.divider()
st.markdown(
    "<center>Made with ❤️ for Leo 🐾</center>",
    unsafe_allow_html=True
)

