from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from functools import wraps
from datetime import datetime, date
import sqlite3, os, math, json, shutil, base64, io
import qrcode

APP_NAME = "DMH / JHIMS Hospital Web"
HOSPITAL_NAME = "DUNKWA MUNICIPAL HOSPITAL"
HOSPITAL_ADDRESS = "P.O.BOX 49 DUNKWA-ON-OFFIN"
HOSPITAL_PHONE = ""
POWERED_BY = "Powered by JACKSTIDIOS @ {year}".format(year=datetime.now().year)

DB_PATH = os.path.join(os.path.dirname(__file__), "hospital_web.db")

DEFAULT_RECEIPT_PREFIX = "DMH"
DEFAULT_EMBALMING_FEE = 350.0
DEFAULT_DAILY_RATE = 16.0

BUILTIN_SERVICES = [
    "OPD","INVESTIGATION","PHARMACY","IPD","DRESSING","MORTUARY","OBS","DENTAL",
    "EYE","ULTRASOUND","ANC","OXYGEN","ENT","EMERGENCY","X-RAY","ECG"
]

BUILTIN_LAB_TESTS = [
    ("Full Blood Count (FBC)", 30.0, 50.0),
    ("ANC LABS", 80.0, 330.0),
    ("BF Malaria", 0.0, 20.0),
    ("UPT", 10.0, 20.0),
    ("LFT", 60.0, 80.0),
    ("RFT", 70.0, 90.0),
    ("BUE CR", 70.0, 90.0),
    ("LIPID PROFILE", 50.0, 70.0),
    ("HB", 0.0, 20.0),
    ("SICKLING", 0.0, 20.0),
    ("BLOOD GROUPING", 0.0, 20.0),
    ("G6PD", 0.0, 50.0),
    ("HBSAG", 0.0, 20.0),
    ("HCV", 0.0, 30.0),
    ("VDRL", 0.0, 20.0),
    ("TYPHOID", 30.0, 50.0),
    ("H.PYLORI", 30.0, 50.0),
    ("S.BILIRUBIN", 30.0, 50.0),
    ("URIC ACID", 30.0, 50.0),
    ("URINE R/E", 0.0, 20.0),
]

app = Flask(__name__)
app.secret_key = "CHANGE_ME_SECRET_KEY"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.context_processor
def inject_hospital():
    return dict(hospital=get_hospital())

def init_settings():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS hospital_settings (
            id INTEGER PRIMARY KEY,
            hospital_name TEXT,
            address TEXT,
            phone TEXT,
            logo TEXT
        )
    """)
    conn.commit()
    conn.close()

def init_db():
    conn = get_db()
    c = conn.cursor()

def init_ipd():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS ipd (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            patient_name TEXT,
            age TEXT,
            sex TEXT,
            diagnosis TEXT,
            doctor TEXT,
            ward TEXT,
            bed TEXT,
            admission_date TEXT,
            status TEXT DEFAULT 'Admitted'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ipd_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_id INTEGER,
            service_name TEXT,
            amount REAL,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()

    c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")

    c.execute(
        "CREATE TABLE IF NOT EXISTS users("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "username TEXT UNIQUE,"
        "password TEXT,"
        "role TEXT)"
    )

# ================= MORTUARY SETTINGS =================
    c.execute("""
        CREATE TABLE IF NOT EXISTS mortuary_settings(
        id INTEGER PRIMARY KEY,
        embalming_fee REAL,
        week1_rate REAL,
        week2_rate REAL,
        week3_rate REAL
    )
    """)

    c.execute("SELECT COUNT(*) FROM mortuary_settings")
    if c.fetchone()[0] == 0:
       c.execute("""
        INSERT INTO mortuary_settings 
        (embalming_fee, week1_rate, week2_rate, week3_rate)
        VALUES (350, 16, 13, 10)
    """)

    c.execute(
        "CREATE TABLE IF NOT EXISTS patient_records("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "date TEXT,"
        "receipt_number TEXT,"
        "patient_id TEXT,"
        "patient_name TEXT,"
        "service_received TEXT,"
        "amount_paid REAL,"
        "amount_in_words TEXT,"
        "cashier_name TEXT,"
        "payment_method TEXT,"
        "details TEXT)"
    )

    c.execute(
        "CREATE TABLE IF NOT EXISTS lab_requests("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "created_at TEXT,"
        "patient_id TEXT,"
        "patient_name TEXT,"
        "age TEXT,"
        "insured_status TEXT,"
        "tests_json TEXT,"
        "total_amount REAL,"
        "invoice_no TEXT,"
        "is_paid INTEGER DEFAULT 0,"
        "results_json TEXT,"
        "results_at TEXT)"
    )

    c.execute(
        "CREATE TABLE IF NOT EXISTS mortuary_cases("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "corpse_id TEXT UNIQUE,"
        "patient_id TEXT,"
        "corpse_name TEXT,"
        "sex TEXT,"
        "age TEXT,"
        "relative_name TEXT,"
        "relative_phone TEXT,"
        "deposit_date TEXT,"
        "release_date TEXT,"
        "days_total INTEGER,"
        "daily_rate REAL,"
        "embalming_fee REAL,"
        "extra_items TEXT,"
        "extra_amount REAL,"
        "total_amount REAL,"
        "status TEXT,"
        "is_paid INTEGER DEFAULT 0)"
    )

        

    c.execute(
        "CREATE TABLE IF NOT EXISTS lab_test_prices("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "name TEXT UNIQUE,"
        "insured_price REAL,"
        "non_insured_price REAL)"
    )

    c.execute(
        "CREATE TABLE IF NOT EXISTS services("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "name TEXT UNIQUE)"
    )

    c.execute(
        "CREATE TABLE IF NOT EXISTS activity_log("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "timestamp TEXT,"
        "username TEXT,"
        "action TEXT,"
        "details TEXT)"
    )

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            [
                ("admin", "admin123", "Admin"),
                ("cashier", "cashier123", "Cashier"),
                ("lab", "lab123", "Lab"),
                ("mortuary", "mortuary123", "Mortuary"),
                ("reports", "reports123", "Reports"),
            ],
        )

    c.execute("SELECT COUNT(*) FROM lab_test_prices")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO lab_test_prices(name,insured_price,non_insured_price) VALUES(?,?,?)",
            BUILTIN_LAB_TESTS,
        )

    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO services(name) VALUES(?)", [(s,) for s in BUILTIN_SERVICES])

    conn.commit()
    conn.close()

def log_activity(username, action, details=""):
    conn = get_db()
    c = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO activity_log(timestamp,username,action,details) VALUES(?,?,?,?)",
        (ts, username, action, details),
    )
    conn.commit()
    conn.close()


def get_meta(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM meta WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default


def set_meta(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
TENS = [
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
]


def _chunk_to_words(n):
    parts = []
    if n >= 100:
        parts.append(ONES[n // 100])
        parts.append("Hundred")
        n %= 100
        if n:
            parts.append("and")
    if n >= 20:
        parts.append(TENS[n // 10])
        if n % 10:
            parts.append(ONES[n % 10])
    elif n > 0:
        parts.append(ONES[n])
    return " ".join(parts) if parts else "Zero"


def number_to_words(n):
    if n == 0:
        return "Zero"
    parts = []
    for label, unit in [("Billion", 1_000_000_000), ("Million", 1_000_000), ("Thousand", 1000)]:
        chunk = n // unit
        if chunk:
            parts.append(_chunk_to_words(chunk))
            parts.append(label)
            n %= unit
    if n:
        parts.append(_chunk_to_words(n))
    return " ".join(parts)


def amount_to_words(amount):
    if amount < 0:
        return "Minus " + amount_to_words(-amount)
    cedis = int(math.floor(amount))
    pesewas = int(round((amount - cedis) * 100))
    parts = []
    if cedis:
        parts.append(number_to_words(cedis))
        parts.append("Ghana Cedis")
    else:
        parts.append("Zero Ghana Cedis")
    if pesewas:
        parts.append("and")
        parts.append(number_to_words(pesewas))
        parts.append("Pesewas")
    parts.append("Only")
    return " ".join(parts)


def get_receipt_prefix():
    return get_meta("receipt_prefix", DEFAULT_RECEIPT_PREFIX) or DEFAULT_RECEIPT_PREFIX


def generate_receipt_number():
    prefix = get_receipt_prefix()
    last = get_meta("receipt_last", prefix + "/0000000") or prefix + "/0000000"
    if "/" in last:
        _, num = last.split("/", 1)
        sep = "/"
    else:
        num = last[len(prefix) :]
        sep = ""
    try:
        seq = int(num) + 1
        width = len(num)
    except Exception:
        seq = 1
        width = 7
    new = f"{seq:0{width}d}"
    receipt = f"{prefix}{sep}{new}"
    set_meta("receipt_last", receipt)
    return receipt


def generate_lab_invoice():
    last = get_meta("lab_inv_last", "INV000000") or "INV000000"
    prefix = "INV"
    num = last.replace(prefix, "")
    try:
        seq = int(num) + 1
        width = len(num)
    except Exception:
        seq = 1
        width = 6
    new = f"{seq:0{width}d}"
    inv = f"{prefix}{new}"
    set_meta("lab_inv_last", inv)
    return inv



def generate_corpse_id():
    last = get_meta("corpse_last", "C0000") or "C0000"
    prefix = "".join(ch for ch in last if not ch.isdigit()) or "C"
    num = "".join(ch for ch in last if ch.isdigit()) or "0"
    try:
        seq = int(num) + 1
        width = max(len(num), 4)
    except Exception:
        seq = 1
        width = 4
    new = f"{seq:0{width}d}"
    cid = prefix + new
    set_meta("corpse_last", cid)
    return cid


def calculate_bill(deposit_date):
    settings = get_mortuary_settings()

    from datetime import datetime
    d1 = datetime.strptime(deposit_date, "%Y-%m-%d")
    d2 = datetime.today()

    days = (d2 - d1).days or 1

    total = 0

    for d in range(1, days+1):
        if d <= 7:
            total += settings["week1_rate"]
        elif d <= 14:
            total += settings["week2_rate"]
        else:
            total += settings["week3_rate"]

    return days, total

def get_hospital():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM hospital_settings LIMIT 1")
    data = c.fetchone()
    conn.close()
    return data

def login_required(role=None):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") not in (role, "Admin"):
                flash("Access denied for your role.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)

        return wrapper

    return deco


@app.before_request
def startup():
    init_db()


@app.context_processor
def inject_globals():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, insured_price, non_insured_price FROM lab_test_prices ORDER BY name")
    tests = c.fetchall()
    c.execute("SELECT name FROM services ORDER BY name")
    services = [r["name"] for r in c.fetchall()]
    conn.close()
    return dict(
        APP_NAME=APP_NAME,
        HOSPITAL_NAME=HOSPITAL_NAME,
        HOSPITAL_ADDRESS=HOSPITAL_ADDRESS,
        HOSPITAL_PHONE=HOSPITAL_PHONE,
        POWERED_BY=POWERED_BY,
        LAB_TESTS=tests,
        SERVICES=services,
        now=datetime.now,
    )




def generate_qr(data: str) -> str:
    """Generate a QR code PNG as base64 string. Requires qrcode and pillow."""
    try:
        img = qrcode.make(data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            log_activity(user["username"], "LOGIN", "User logged in")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        log_activity(session["user"], "LOGOUT", "User logged out")
    session.clear()
    return redirect(url_for("login"))


@app.route("/ipd")
@login_required()
def ipd():
    return render_template("ipd.html")


@app.route("/dashboard")
@login_required()
def dashboard():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount_paid),0) FROM patient_records WHERE date=?", (today,))
    total_today = c.fetchone()[0]

    # optional patient history timeline
    pid = request.args.get("patient_id", "").strip()
    timeline = []
    if pid:
        # receipts
        c.execute("SELECT date, time('now') as t, 'Receipt' as source, receipt_number as ref, service_received as label, amount_paid as amount FROM patient_records WHERE patient_id=? ORDER BY id DESC LIMIT 20", (pid,))
        timeline += [dict(row) for row in c.fetchall()]
        # lab invoices
        c.execute("SELECT substr(created_at,1,10) as date, substr(created_at,12,8) as t, 'Lab' as source, invoice_no as ref, 'Lab invoice' as label, total_amount as amount FROM lab_requests WHERE patient_id=? ORDER BY id DESC LIMIT 20", (pid,))
        timeline += [dict(row) for row in c.fetchall()]
        # mortuary
        c.execute("SELECT deposit_date as date, '00:00:00' as t, 'Mortuary' as source, corpse_id as ref, status as label, total_amount as amount FROM mortuary_cases WHERE patient_id=? ORDER BY id DESC LIMIT 20", (pid,))
        timeline += [dict(row) for row in c.fetchall()]
        # sort in python by date + time desc
        def sort_key(item):
            return (item.get("date") or "", item.get("t") or "")
        timeline.sort(key=sort_key, reverse=True)
    conn.close()
    return render_template("dashboard.html", total_today=total_today, today=today, patient_id=pid, timeline=timeline)



@app.route("/cashier", methods=["GET", "POST"])
@login_required(role="Cashier")
def cashier():
    conn = get_db()
    c = conn.cursor()

    prefill = None

    # ================= GET PARAMETERS =================
    load_pid = request.args.get("load_pid", "").strip()
    corpse_id = request.args.get("corpse_id", "").strip()

    # ================= LOAD FROM MORTUARY (BY CORPSE ID) =================
    if corpse_id:
        c.execute("SELECT * FROM mortuary_cases WHERE corpse_id=?", (corpse_id,))
        m = c.fetchone()

        if m:
            prefill = {
                "patient_id": m["patient_id"],
                "patient_name": m["corpse_name"],
                "service_received": "Mortuary",
                "amount_paid": m["total_amount"],
                "details": f"Mortuary bill for {m['corpse_name']} (Corpse ID: {m['corpse_id']})"
            }

    # ================= LOAD FROM LAB OR MORTUARY (BY PATIENT ID) =================
    elif load_pid:
        # ---- LAB FIRST ----
        c.execute(
            "SELECT * FROM lab_requests WHERE patient_id=? AND is_paid=0 ORDER BY id DESC LIMIT 1",
            (load_pid,)
        )
        lab_row = c.fetchone()

        if lab_row:
            prefill = {
                "patient_id": lab_row["patient_id"],
                "patient_name": lab_row["patient_name"],
                "service_received": "INVESTIGATION",
                "amount_paid": lab_row["total_amount"],
                "details": f"LAB INVOICE {lab_row['invoice_no']}"
            }
        else:
            # ---- MORTUARY ----
            c.execute(
                "SELECT * FROM mortuary_cases WHERE patient_id=? AND is_paid=0 ORDER BY id DESC LIMIT 1",
                (load_pid,)
            )
            m_row = c.fetchone()

            if m_row:
                prefill = {
                    "patient_id": m_row["patient_id"],
                    "patient_name": m_row["corpse_name"],
                    "service_received": "Mortuary",
                    "amount_paid": m_row["total_amount"],
                    "details": f"Mortuary case {m_row['corpse_id']}"
                }

        if not prefill:
            flash("No unpaid Lab or Mortuary record found.", "danger")

    # ================= SAVE PAYMENT =================
    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        patient_name = request.form.get("patient_name", "").strip()
        service_received = request.form.get("service_received", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        amount_str = request.form.get("amount_paid", "0").strip()
        details = request.form.get("details", "").strip()

        if not patient_name or not service_received or not amount_str:
            flash("Fill patient, service and amount.", "danger")
        else:
            try:
                amount = float(amount_str)
            except:
                amount = 0.0

            receipt = generate_receipt_number()
            amount_words = amount_to_words(amount)
            today = datetime.now().strftime("%Y-%m-%d")
            cashier_name = session.get("user")

            c.execute(
                "INSERT INTO patient_records("
                "date,receipt_number,patient_id,patient_name,service_received,"
                "amount_paid,amount_in_words,cashier_name,payment_method,details"
                ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    today,
                    receipt,
                    patient_id,
                    patient_name,
                    service_received,
                    amount,
                    amount_words,
                    cashier_name,
                    payment_method,
                    details,
                ),
            )

            # ================= MARK LAB AS PAID =================
            if service_received == "INVESTIGATION":
                c.execute(
                    "UPDATE lab_requests SET is_paid=1 WHERE patient_id=? AND is_paid=0",
                    (patient_id,)
                )

            # ================= MARK MORTUARY AS PAID =================
            if service_received == "Mortuary":
                c.execute(
                    "UPDATE mortuary_cases SET is_paid=1 WHERE patient_id=? AND total_amount > 0",
                    (patient_id,)
                )

            conn.commit()
            rec_id = c.lastrowid

            log_activity(
                cashier_name,
                "RECEIPT_CREATE",
                f"Receipt {receipt} for {patient_name}",
            )

            flash(f"Receipt saved: {receipt}", "success")
            conn.close()

            return redirect(url_for("receipt_view", rec_id=rec_id))

    # ================= LOAD RECEIPTS =================
    q = request.args.get("q", "").strip()

    if q:
        c.execute(
            "SELECT * FROM patient_records "
            "WHERE patient_name LIKE ? OR receipt_number LIKE ? OR patient_id LIKE ? "
            "ORDER BY id DESC LIMIT 100",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        )
    else:
        c.execute("SELECT * FROM patient_records ORDER BY id DESC LIMIT 50")

    rows = c.fetchall()
    conn.close()

    return render_template("cashier.html", rows=rows, q=q, prefill=prefill)

@app.route("/receipt/<int:rec_id>")

@login_required()
def receipt_view(rec_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM patient_records WHERE id=?", (rec_id,))
    rec = c.fetchone()
    conn.close()
    if not rec:
        flash("Receipt not found.", "danger")
        return redirect(url_for("cashier"))
    return render_template("receipt.html", rec=rec)


@app.route("/settings/hospital", methods=["GET", "POST"])
@login_required()
def hospital_settings():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["hospital_name"]
        address = request.form["address"]
        phone = request.form["phone"]
        logo = request.form["logo"]

        c.execute("DELETE FROM hospital_settings")
        c.execute("""
            INSERT INTO hospital_settings (hospital_name, address, phone, logo)
            VALUES (?, ?, ?, ?)
        """, (name, address, phone, logo))
        conn.commit()

    c.execute("SELECT * FROM hospital_settings LIMIT 1")
    data = c.fetchone()
    conn.close()

    return render_template("hospital_settings.html", data=data)


@app.route("/cashier/edit/<int:rec_id>", methods=["GET", "POST"])
@login_required(role="Admin")
def edit_receipt(rec_id):
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        patient_name = request.form.get("patient_name", "").strip()
        service_received = request.form.get("service_received", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        amount_str = request.form.get("amount_paid", "0").strip()
        details = request.form.get("details", "").strip()
        try:
            amount = float(amount_str)
        except Exception:
            amount = 0.0
        amount_words = amount_to_words(amount)
        c.execute(
            "UPDATE patient_records SET patient_id=?,patient_name=?,service_received=?,"
            "amount_paid=?,amount_in_words=?,payment_method=?,details=? WHERE id=?",
            (
                patient_id,
                patient_name,
                service_received,
                amount,
                amount_words,
                payment_method,
                details,
                rec_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Receipt updated.", "success")
        return redirect(url_for("cashier"))
    c.execute("SELECT * FROM patient_records WHERE id=?", (rec_id,))
    rec = c.fetchone()
    conn.close()
    if not rec:
        flash("Receipt not found.", "danger")
        return redirect(url_for("cashier"))
    return render_template("edit_receipt.html", rec=rec)


@app.route("/cashier/delete/<int:rec_id>", methods=["POST"])
@login_required(role="Admin")
def delete_receipt(rec_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM patient_records WHERE id=?", (rec_id,))
    conn.commit()
    conn.close()
    flash("Receipt deleted.", "success")
    return redirect(url_for("cashier"))



@app.route("/lab", methods=["GET", "POST"])
@login_required(role="Lab")
def lab():
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        patient_name = request.form.get("patient_name", "").strip()
        age = request.form.get("age", "").strip()
        insured_status = request.form.get("insured_status", "Non-insured")
        tests_json = request.form.get("tests_json", "[]")
        total_str = request.form.get("total_amount", "0").strip()
        if not patient_name or tests_json == "[]":
            flash("Enter patient and select at least one test.", "danger")
        else:
            try:
                total = float(total_str)
            except Exception:
                total = 0.0
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            invoice = generate_lab_invoice()
            c.execute(
                "INSERT INTO lab_requests("
                "created_at,patient_id,patient_name,age,insured_status,"
                "tests_json,total_amount,invoice_no,is_paid,results_json,results_at"
                ") VALUES(?,?,?,?,?,?,?,?,0,NULL,NULL)",
                (
                    created_at,
                    patient_id,
                    patient_name,
                    age,
                    insured_status,
                    tests_json,
                    total,
                    invoice,
                ),
            )
            conn.commit()
            req_id = c.lastrowid
            log_activity(session.get("user"), "LAB_REQUEST", f"Invoice {invoice} for {patient_name}")
            conn.close()
            flash(f"Lab request saved. Invoice {invoice}", "success")
            return redirect(url_for("lab_invoice", req_id=req_id))

    # filters/search
    q = request.args.get("q", "").strip()
    today = datetime.now().strftime("%Y-%m-%d")
    if q:
        c.execute(
            "SELECT * FROM lab_requests WHERE patient_name LIKE ? OR patient_id LIKE ? OR invoice_no LIKE ? "
            "ORDER BY id DESC LIMIT 100",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        )
    else:
        c.execute("SELECT * FROM lab_requests ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()

    # today's summary
    c.execute("SELECT COALESCE(SUM(total_amount),0) FROM lab_requests WHERE substr(created_at,1,10)=?", (today,))
    today_total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM lab_requests WHERE substr(created_at,1,10)=?", (today,))
    today_count = c.fetchone()[0]

    conn.close()
    return render_template("lab.html", rows=rows, q=q, today_total=today_total, today_count=today_count, today=today)


@app.route("/lab/invoice/<int:req_id>")
@login_required(role="Lab")
def lab_invoice(req_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM lab_requests WHERE id=?", (req_id,))
    req = c.fetchone()
    conn.close()
    if not req:
        flash("Lab request not found.", "danger")
        return redirect(url_for("lab"))
    try:
        tests = json.loads(req["tests_json"] or "[]")
    except Exception:
        tests = []
    return render_template("lab_invoice.html", req=req, tests=tests)


@app.route("/lab/results/<int:req_id>", methods=["GET", "POST"])
@login_required(role="Lab")
def lab_results(req_id):
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        results_json = request.form.get("results_json", "[]")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "UPDATE lab_requests SET results_json=?,results_at=? WHERE id=?",
            (results_json, ts, req_id),
        )
        conn.commit()
        conn.close()
        flash("Lab results saved.", "success")
        return redirect(url_for("lab_results", req_id=req_id))
    c.execute("SELECT * FROM lab_requests WHERE id=?", (req_id,))
    req = c.fetchone()
    conn.close()
    if not req:
        flash("Lab request not found.", "danger")
        return redirect(url_for("lab"))
    try:
        tests = json.loads(req["tests_json"] or "[]")
    except Exception:
        tests = []
    try:
        results = json.loads(req["results_json"] or "[]")
    except Exception:
        results = []
    return render_template("lab_results.html", req=req, tests=tests, results=results)


@app.route("/lab/verify-payment", methods=["POST"])
@login_required(role="Lab")
def lab_verify_payment():
    pid = request.form.get("patient_id_verify", "").strip()
    if not pid:
        flash("Enter patient ID.", "danger")
        return redirect(url_for("lab"))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM patient_records WHERE patient_id=?", (pid,))
    count = c.fetchone()[0]
    conn.close()
    if count:
        flash(f"Payment found for Patient ID {pid}.", "success")
    else:
        flash(f"No payment yet for Patient ID {pid}.", "danger")
    return redirect(url_for("lab"))

def get_mortuary_settings():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM mortuary_settings LIMIT 1")
    row = c.fetchone()

    conn.close()

    if row:
        return dict(row)
    else:
        # default values
        return {
            "embalming_fee": 350,
            "week1_rate": 16,
            "week2_rate": 13,
            "week3_rate": 10
        }


@app.route("/mortuary", methods=["GET", "POST"])
@login_required(role="Mortuary")
def mortuary():
    conn = get_db()
    c = conn.cursor()

    # ================= SAVE =================
    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        corpse_name = request.form.get("corpse_name", "").strip()
        sex = request.form.get("sex", "").strip()
        age = request.form.get("age", "").strip()
        relative_name = request.form.get("relative_name", "").strip()
        relative_phone = request.form.get("relative_phone", "").strip()
        deposit_date = request.form.get("deposit_date", "").strip()
        release_date = request.form.get("release_date", "").strip() or None
        extra_items = request.form.get("extra_items", "").strip()
        extra_amount = request.form.get("extra_amount", "0").strip()
        status = request.form.get("status", "In-Mortuary")

        if not corpse_name or not deposit_date:
            flash("Fill corpse name and deposit date.", "danger")
        else:
            settings = get_mortuary_settings()

            embalming_fee = settings["embalming_fee"]

            # 👉 FIX: define days
            days = 1

            try:
                extra = float(extra_amount or 0)
            except:
                extra = 0

            total = embalming_fee + extra

            cid = generate_corpse_id()

            c.execute("""
                INSERT INTO mortuary_cases(
                corpse_id, patient_id, corpse_name, sex, age,
                relative_name, relative_phone,
                deposit_date, release_date,
                days_total, daily_rate, embalming_fee,
                extra_items, extra_amount, total_amount,
                status, is_paid
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """, (
                cid,
                patient_id,
                corpse_name,
                sex,
                age,
                relative_name,
                relative_phone,
                deposit_date,
                release_date,
                days,
                0,
                embalming_fee,
                extra_items,
                extra,
                total,
                status,
            ))

            conn.commit()
            flash(f"Saved. Corpse ID: {cid}", "success")

    # ================= FETCH =================
    c.execute("SELECT * FROM mortuary_cases ORDER BY id DESC")
    rows = c.fetchall()

    cases = []

    for r in rows:
        days, bill = calculate_mortuary_bill(r["deposit_date"])

        case = dict(r)
        case["live_days"] = days
        case["live_bill"] = bill

        cases.append(case)

    conn.close()

    return render_template("mortuary.html", rows=cases)


@app.route("/mortuary/release-id", methods=["POST"])
@login_required(role="Mortuary")
def mortuary_release_by_id():
    cid = request.form.get("corpse_id_lookup", "").strip()

    if not cid:
        flash("Enter Corpse ID.", "danger")
        return redirect(url_for("mortuary"))

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT id FROM mortuary_cases WHERE corpse_id=?", (cid,))
    row = c.fetchone()
    conn.close()

    if not row:
        flash("Corpse ID not found.", "danger")
        return redirect(url_for("mortuary"))

    return redirect(url_for("mortuary_invoice", case_id=row["id"]))


@app.route("/mortuary/release/<int:case_id>", methods=["GET", "POST"])
@login_required(role="Mortuary")
def mortuary_release(case_id):
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        release_date = request.form.get("release_date", "").strip()
        extra_items = request.form.get("extra_items", "").strip()
        extra_amount = request.form.get("extra_amount", "0").strip()
        c.execute("SELECT * FROM mortuary_cases WHERE id=?", (case_id,))
        m = c.fetchone()
        if not m:
            conn.close()
            flash("Case not found.", "danger")
            return redirect(url_for("mortuary"))
        days, total = calc_mortuary_bill(m["deposit_date"], release_date, extra_amount)
        daily_rate = float(get_meta("mort_daily_rate", DEFAULT_DAILY_RATE) or DEFAULT_DAILY_RATE)
        embalming_fee = float(
            get_meta("embalming_fee", DEFAULT_EMBALMING_FEE) or DEFAULT_EMBALMING_FEE
        )
        try:
            extra = float(extra_amount or 0)
        except Exception:
            extra = 0.0
        c.execute(
            "UPDATE mortuary_cases SET release_date=?,days_total=?,daily_rate=?,embalming_fee=?,"
            "extra_items=?,extra_amount=?,total_amount=?,status=? WHERE id=?",
            (
                release_date,
                days,
                daily_rate,
                embalming_fee,
                extra_items,
                extra,
                total,
                "Released",
                case_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Release data saved and bill updated.", "success")
        return redirect(url_for("mortuary_invoice", case_id=case_id))
    c.execute("SELECT * FROM mortuary_cases WHERE id=?", (case_id,))
    case = c.fetchone()
    conn.close()
    if not case:
        flash("Case not found.", "danger")
        return redirect(url_for("mortuary"))
    return render_template("mortuary_release.html", case=case)


@app.route("/mortuary/invoice/<int:case_id>")
@login_required(role="Mortuary")
def mortuary_invoice(case_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM mortuary_cases WHERE id=?", (case_id,))
    case = c.fetchone()
    conn.close()
    if not case:
        flash("Case not found.", "danger")
        return redirect(url_for("mortuary"))
    return render_template("mortuary_invoice.html", case=case)


def reports_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("role") not in ("Admin", "Reports", "Cashier"):
            flash("Access denied to reports.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)

    return wrapper

# =========================
# VIEW
# =========================
@app.route("/mortuary/view/<int:id>")
@login_required(role="Mortuary")
def mortuary_view(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM mortuary_cases WHERE id=?", (id,))
    r = c.fetchone()
    conn.close()

    if not r:
        return "Record not found"

    return render_template("mortuary_view.html", r=r)

# =========================
# DELETE
# =========================
@app.route("/mortuary/delete/<int:id>")
@login_required(role="Mortuary")
def delete_mortuary(id):
    conn = get_db()
    conn.execute("DELETE FROM mortuary_cases WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/mortuary")


# =========================
# DISCHARGE BUTTON
# =========================
@app.route("/mortuary/discharge/<int:id>", methods=["GET", "POST"])
@login_required(role="Mortuary")
def discharge(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM mortuary_cases WHERE id=?", (id,))
    r = c.fetchone()
    conn.close()

    if not r:
        return "Record not found"

    if r["is_paid"] == 0:
        return "⚠️ Pay embalming fee first"

    # 🚨 BLOCK IF NOT PAID
    if r["is_paid"] == 0:
        return "⚠️ Cannot discharge. Payment not completed."

    return render_template("mortuary_release.html", case=r)

    days, bill = calculate_mortuary_bill(r["deposit_date"])

    extra = float(r["extra_amount"] or 0)

    total_amount = bill + extra

@app.route("/reports")
@reports_required
def reports_home():
    return render_template("reports_home.html")


@app.route("/reports/patient", methods=["GET", "POST"])
@reports_required
def reports_patient():
    rows = []
    total = 0.0
    start = end = None
    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        if start and end:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT * FROM patient_records WHERE date BETWEEN ? AND ? ORDER BY date,id",
                (start, end),
            )
            rows = c.fetchall()
            c.execute(
                "SELECT COALESCE(SUM(amount_paid),0) FROM patient_records WHERE date BETWEEN ? AND ?",
                (start, end),
            )
            total = c.fetchone()[0]
            conn.close()
    return render_template("reports_patient.html", rows=rows, total=total, start=start, end=end)


@app.route("/reports/services", methods=["GET", "POST"])
@reports_required
def reports_services():
    rows = []
    grand = 0.0
    start = end = None
    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        if start and end:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT service_received,COUNT(*) as count_rec, SUM(amount_paid) as total_amount "
                "FROM patient_records WHERE date BETWEEN ? AND ? "
                "GROUP BY service_received ORDER BY service_received",
                (start, end),
            )
            rows = c.fetchall()
            c.execute(
                "SELECT COALESCE(SUM(amount_paid),0) FROM patient_records WHERE date BETWEEN ? AND ?",
                (start, end),
            )
            grand = c.fetchone()[0]
            conn.close()
    return render_template(
        "reports_services.html", rows=rows, grand=grand, start=start, end=end
    )


@app.route("/reports/mortuary", methods=["GET", "POST"])
@reports_required
def reports_mortuary():
    rows = []
    total = 0.0
    start = end = None
    if request.method == "POST":
        start = request.form.get("start")
        end = request.form.get("end")
        if start and end:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                "SELECT * FROM mortuary_cases WHERE deposit_date BETWEEN ? AND ? "
                "ORDER BY deposit_date,id",
                (start, end),
            )
            rows = c.fetchall()
            c.execute(
                "SELECT COALESCE(SUM(total_amount),0) FROM mortuary_cases WHERE deposit_date BETWEEN ? AND ?",
                (start, end),
            )
            total = c.fetchone()[0]
            conn.close()
    return render_template("reports_mortuary.html", rows=rows, total=total, start=start, end=end)

@app.route("/mortuary/settings", methods=["GET","POST"])
def mortuary_settings():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        embalming = request.form["embalming_fee"]
        w1 = request.form["week1"]
        w2 = request.form["week2"]
        w3 = request.form["week3"]

        c.execute("""
        UPDATE mortuary_settings
        SET embalming_fee=?, week1_rate=?, week2_rate=?, week3_rate=?
        """, (embalming, w1, w2, w3))

        conn.commit()

    c.execute("SELECT * FROM mortuary_settings LIMIT 1")
    s = c.fetchone()
    conn.close()

    return render_template("mortuary_settings.html", s=s)

from datetime import datetime

def calculate_mortuary_bill(deposit_date):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM mortuary_settings LIMIT 1")
    s = c.fetchone()

    week1 = s["week1_rate"]
    week2 = s["week2_rate"]
    week3 = s["week3_rate"]

    d1 = datetime.strptime(deposit_date, "%Y-%m-%d")
    d2 = datetime.today()

    days = (d2 - d1).days
    if days <= 0:
        days = 1

    total = 0

    for day in range(1, days + 1):
        if day <= 7:
            total += week1
        elif day <= 14:
            total += week2
        else:
            total += week3

    conn.close()
    return days, total


@app.route("/admin/users", methods=["GET", "POST"])
@login_required(role="Admin")
def manage_users():
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip() or "Cashier"
        if username and password:
            try:
                c.execute(
                    "INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    (username, password, role),
                )
                conn.commit()
                flash("User added.", "success")
                log_activity(session.get("user"), "USER_ADD", f"Added {username}")
            except sqlite3.IntegrityError:
                flash("Username already exists.", "danger")
        else:
            flash("Enter username and password.", "danger")
    c.execute("SELECT * FROM users ORDER BY username")
    users = c.fetchall()
    conn.close()
    return render_template("manage_users.html", users=users)


@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required(role="Admin")
def edit_user(user_id):
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "").strip()
        if password:
            c.execute("UPDATE users SET password=?,role=? WHERE id=?", (password, role, user_id))
        else:
            c.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        conn.commit()
        conn.close()
        flash("User updated.", "success")
        return redirect(url_for("manage_users"))
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("manage_users"))
    return render_template("edit_user.html", user=user)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required(role="Admin")
def delete_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted.", "success")
    return redirect(url_for("manage_users"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required()
def change_password():
    if request.method == "POST":
        current = request.form.get("current", "").strip()
        new = request.form.get("new", "").strip()
        if not new:
            flash("Enter new password.", "danger")
            return redirect(url_for("change_password"))
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (session.get("user"), current),
        )
        row = c.fetchone()
        if not row:
            conn.close()
            flash("Current password incorrect.", "danger")
            return redirect(url_for("change_password"))
        c.execute(
            "UPDATE users SET password=? WHERE username=?", (new, session.get("user"))
        )
        conn.commit()
        conn.close()
        flash("Password changed.", "success")
        return redirect(url_for("dashboard"))
    return render_template("change_password.html")


@app.route("/settings/receipt", methods=["GET", "POST"])
@login_required(role="Admin")
def settings_receipt():
    if request.method == "POST":
        prefix = request.form.get("prefix", "").strip() or DEFAULT_RECEIPT_PREFIX
        last = request.form.get("last", "").strip()
        set_meta("receipt_prefix", prefix)
        if last:
            set_meta("receipt_last", last)
        flash("Receipt settings saved.", "success")
    prefix = get_receipt_prefix()
    last = get_meta("receipt_last", prefix + "/0000000")
    return render_template("settings_receipt.html", prefix=prefix, last=last)



@app.route("/settings/theme", methods=["GET", "POST"])
@login_required(role="Admin")
def settings_theme():
    if request.method == "POST":
        theme = request.form.get("theme", "light")
        if theme not in ("light", "luxury"):
            theme = "light"
        set_meta("ui_theme", theme)
        flash("Theme updated.", "success")
    current = get_meta("ui_theme", "light") or "light"
    return render_template("settings_theme.html", current=current)
@app.route("/settings/lab-prices", methods=["GET", "POST"])
@login_required(role="Admin")
def settings_lab_prices():
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        for key, val in request.form.items():
            if key.startswith("ins_") or key.startswith("non_"):
                field, sid = key.split("_", 1)
                try:
                    price = float(val or 0)
                except Exception:
                    price = 0.0
                if field == "ins":
                    c.execute(
                        "UPDATE lab_test_prices SET insured_price=? WHERE id=?",
                        (price, sid),
                    )
                else:
                    c.execute(
                        "UPDATE lab_test_prices SET non_insured_price=? WHERE id=?",
                        (price, sid),
                    )
        conn.commit()
        flash("Lab prices updated.", "success")
    c.execute("SELECT * FROM lab_test_prices ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return render_template("settings_lab_prices.html", rows=rows)


@app.route("/settings/services", methods=["GET", "POST"])
@login_required(role="Admin")
def settings_services():
    conn = get_db()
    c = conn.cursor()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            if name:
                try:
                    c.execute("INSERT INTO services(name) VALUES(?)", (name,))
                    conn.commit()
                    flash("Service added.", "success")
                except sqlite3.IntegrityError:
                    flash("Service already exists.", "danger")
        elif action == "delete":
            sid = request.form.get("service_id")
            c.execute("DELETE FROM services WHERE id=?", (sid,))
            conn.commit()
            flash("Service deleted.", "success")
    c.execute("SELECT * FROM services ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return render_template("settings_services.html", rows=rows)

@app.route("/settings", methods=["GET", "POST"])
@login_required(role="Admin")
def settings():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        name = request.form.get("hospital_name")
        address = request.form.get("address")
        phone = request.form.get("phone")
        logo = request.form.get("logo")

        c.execute("SELECT * FROM hospital_settings LIMIT 1")
        existing = c.fetchone()

        if existing:
            c.execute("""
                UPDATE hospital_settings
                SET hospital_name=?, address=?, phone=?, logo=?
                WHERE id=?
            """, (name, address, phone, logo, existing["id"]))
        else:
            c.execute("""
                INSERT INTO hospital_settings (hospital_name, address, phone, logo)
                VALUES (?, ?, ?, ?)
            """, (name, address, phone, logo))

        conn.commit()
        flash("Settings updated successfully!", "success")

    c.execute("SELECT * FROM hospital_settings LIMIT 1")
    data = c.fetchone()

    conn.close()
    return render_template("settings.html", data=data)


@app.route("/admin/activity")
@login_required(role="Admin")
def activity_log():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT 200")
    rows = c.fetchall()
    conn.close()
    return render_template("activity_log.html", rows=rows)



def bill_consolidation_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("role") not in ("Admin", "Cashier"):
            flash("Access denied to bill consolidation.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/bill-consolidation", methods=["GET", "POST"])
@bill_consolidation_required
def bill_consolidation():
    pid = None
    receipts = []
    labs = []
    morts = []
    total_receipts = total_labs = total_morts = 0.0
    if request.method == "POST":
        pid = request.form.get("patient_id", "").strip()
    else:
        pid = request.args.get("patient_id", "").strip()
    if pid:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM patient_records WHERE patient_id=? ORDER BY date,id", (pid,))
        receipts = c.fetchall()
        c.execute("SELECT * FROM lab_requests WHERE patient_id=? ORDER BY id", (pid,))
        labs = c.fetchall()
        c.execute("SELECT * FROM mortuary_cases WHERE patient_id=? ORDER BY id", (pid,))
        morts = c.fetchall()
        c.execute("SELECT COALESCE(SUM(amount_paid),0) FROM patient_records WHERE patient_id=?", (pid,))
        total_receipts = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(total_amount),0) FROM lab_requests WHERE patient_id=?", (pid,))
        total_labs = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(total_amount),0) FROM mortuary_cases WHERE patient_id=?", (pid,))
        total_morts = c.fetchone()[0]
        conn.close()
    grand = (total_receipts or 0) + (total_labs or 0) + (total_morts or 0)
    return render_template(
        "bill_consolidation.html",
        patient_id=pid,
        receipts=receipts,
        labs=labs,
        morts=morts,
        total_receipts=total_receipts,
        total_labs=total_labs,
        total_morts=total_morts,
        grand=grand,
    )

@app.route("/admin/backup")
@login_required(role="Admin")
def admin_backup():
    if not os.path.exists(DB_PATH):
        flash("Database not found.", "danger")
        return redirect(url_for("dashboard"))
    backup_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"hospital_web_{ts}.db"
    dest = os.path.join(backup_dir, fname)
    shutil.copy2(DB_PATH, dest)
    flash("Backup created: " + fname, "success")
    return send_from_directory(backup_dir, fname, as_attachment=True)

@app.route("/mortuary/generate-bill", methods=["POST"])
@login_required(role="Mortuary")
def generate_mortuary_bill():
    print("GENERATE BILL CLICKED")
    conn = get_db()
    c = conn.cursor()

    corpse_id = request.form.get("corpse_id")

    c.execute("SELECT * FROM mortuary_cases WHERE corpse_id=?", (corpse_id,))
    case = c.fetchone()

    if not case:
        flash("Invalid Corpse ID", "danger")
        return redirect(url_for("mortuary"))

    settings = get_mortuary_settings()

    days, storage_bill = calculate_mortuary_bill(case["deposit_date"])

    embalming_fee = settings["embalming_fee"]

    extra = float(request.form.get("extra_amount") or 0)

    total = storage_bill + embalming_fee + extra

    conn.close()

    return render_template(
        "mortuary.html",
        case=case,
        days=days,
        storage_bill=storage_bill,
        embalming_fee=embalming_fee,
        extra=extra,
        total=total,
        show_bill=True
    )

@app.route("/ipd/admit", methods=["GET", "POST"])
@login_required()
def ipd_admit():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        patient_id = request.form.get("patient_id")
        patient_name = request.form.get("patient_name")
        age = request.form.get("age")
        sex = request.form.get("sex")
        diagnosis = request.form.get("diagnosis")
        doctor = request.form.get("doctor")
        ward = request.form.get("ward")
        bed = request.form.get("bed")
        admission_date = request.form.get("admission_date")

        c.execute("""
            INSERT INTO ipd
            (patient_id, patient_name, age, sex, diagnosis, doctor, ward, bed, admission_date)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            patient_id, patient_name, age, sex,
            diagnosis, doctor, ward, bed, admission_date
        ))

        conn.commit()
        conn.close()

        flash("Patient admitted successfully!", "success")
        return redirect("/ipd")

    return render_template("ipd_admit.html")

@app.route('/ipd/patients')
def ipd_patients():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM ipd ORDER BY id DESC")
    patients = c.fetchall()

    conn.close()

    return render_template("ipd_patients.html", patients=patients)

@app.route('/ipd/discharge/<int:id>')
def discharge_patient(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("UPDATE ipd SET status='Discharged' WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/ipd/patients')

@app.route('/ipd/send_to_cashier/<int:id>')
def send_to_cashier(id):
    return redirect('/cashier')

@app.route('/ipd/send_to_lab/<int:id>')
def send_to_lab(id):
    return redirect('/lab')



if __name__ == "__main__":
    init_settings()   # 👈 ADD THIS LINE
    app.run(debug=True)