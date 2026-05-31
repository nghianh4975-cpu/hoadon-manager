# -*- coding: utf-8 -*-
"""
HOA DON WEB APP - Flask Application
"""

import os
import sqlite3
import uuid
import datetime
import base64
import json
from io import BytesIO
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify

try:
    from werkzeug.security import generate_password_hash, check_password_hash
except:
    import hashlib
    def generate_password_hash(pwd):
        return hashlib.sha256(pwd.encode()).hexdigest()
    def check_password_hash(hashed, pwd):
        return hashed == hashlib.sha256(pwd.encode()).hexdigest()

try:
    import cv2
    import pytesseract
    HAS_OCR = True
except:
    HAS_OCR = False

# ============================================================
# APP CONFIG
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', str(uuid.uuid4()))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Use PostgreSQL on Render, SQLite when local
USE_PG = bool(os.environ.get('DATABASE_URL'))

if USE_PG:
    DATABASE = None  # PostgreSQL doesn't need local file
else:
    DATABASE = os.path.join(BASE_DIR, 'hoadon.db')

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Jinja2 filter
@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value) if value else []
    except:
        return []

# ============================================================
# DATABASE - PostgreSQL tren Render, SQLite khi local
# ============================================================
USE_PG = bool(os.environ.get('DATABASE_URL'))

class HybridCursor:
    def __init__(self, cursor, use_pg):
        self._cursor = cursor
        self._use_pg = use_pg
    def execute(self, sql, params=None):
        if self._use_pg and params:
            sql = sql.replace('?', '%s')
        self._cursor.execute(sql, params)
        return self
    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._use_pg:
            return HybridRow(row)
        return row
    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._use_pg:
            return [HybridRow(r) for r in rows]
        return rows
    def commit(self):
        self._cursor.connection.commit()
    def close(self):
        self._cursor.close()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()
    @property
    def lastrowid(self):
        return getattr(self._cursor, 'lastrowid', None)

class HybridRow:
    def __init__(self, row):
        self._row = row
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._row.values())[key]
        return self._row[key]
    def __len__(self):
        return len(self._row)
    def __iter__(self):
        return iter(self._row)
    def keys(self):
        return self._row.keys()

class HybridConn:
    def __init__(self, conn, use_pg):
        self._conn = conn
        self._use_pg = use_pg
    def cursor(self):
        return HybridCursor(self._conn.cursor(), self._use_pg)
    def commit(self):
        self._conn.commit()
    def close(self):
        self._conn.close()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()

def get_db():
    if USE_PG:
        import psycopg2
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
    return HybridConn(conn, USE_PG)

def init_db():
    conn = get_db()
    c = conn.cursor()
    if USE_PG:
        # PostgreSQL schema
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'ketoan',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            invoice_number VARCHAR(255),
            date VARCHAR(20),
            store_name VARCHAR(255),
            items TEXT,
            subtotal REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            tax_percent REAL DEFAULT 0,
            total REAL DEFAULT 0,
            notes TEXT,
            image_data TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS finances (
            id SERIAL PRIMARY KEY,
            type VARCHAR(20) NOT NULL,
            date VARCHAR(20) NOT NULL,
            amount REAL NOT NULL,
            category VARCHAR(255),
            reason TEXT,
            description TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            message TEXT,
            invoice_id INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('SELECT COUNT(*) FROM users')
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)',
                      ('admin', generate_password_hash('admin123'), 'admin'))
    else:
        # SQLite schema
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'ketoan',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            date TEXT,
            store_name TEXT,
            items TEXT,
            subtotal REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            tax_percent REAL DEFAULT 0,
            total REAL DEFAULT 0,
            notes TEXT,
            image_data TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            reason TEXT,
            description TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            invoice_id INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('SELECT COUNT(*) FROM users')
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                      ('admin', generate_password_hash('admin123'), 'admin'))

    conn.commit()
    conn.close()

# ============================================================
# AUTH
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Ban khong co quyen!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# Context processor - tu dong truyen notif_count vao moi template
@app.context_processor
def inject_user():
    if 'user_id' not in session:
        return {'notif_count': 0}
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],))
    count = c.fetchone()[0]
    conn.close()
    return {'notif_count': count}

@app.before_request
def before():
    pass

# ============================================================
# ROUTES - AUTH
# ============================================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Chao muon {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Dang nhap that bai!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE id = ?', (session['user_id'],))
        user = c.fetchone()

        if not check_password_hash(user['password'], current):
            flash('Mat khau cu khong dung!', 'danger')
            conn.close()
            return render_template('change_password.html')

        if new_pass != confirm:
            flash('Mat khau moi khong khop!', 'danger')
            conn.close()
            return render_template('change_password.html')

        c.execute('UPDATE users SET password = ? WHERE id = ?',
                  (generate_password_hash(new_pass), session['user_id']))
        conn.commit()
        conn.close()
        flash('Doi mat khau thanh cong!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')

# ============================================================
# ROUTES - DASHBOARD
# ============================================================
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.cursor()

    today = datetime.date.today().strftime('%Y-%m-%d')
    month_start = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')

    c.execute('SELECT COUNT(*), COALESCE(SUM(total),0) FROM invoices WHERE date = ?', (today,))
    t = c.fetchone()
    today_count, today_total = t[0], t[1]

    c.execute('SELECT COUNT(*), COALESCE(SUM(total),0) FROM invoices WHERE date >= ?', (month_start,))
    t = c.fetchone()
    month_count, month_total = t[0], t[1]

    c.execute('SELECT COALESCE(SUM(amount),0) FROM finances WHERE type="revenue" AND date >= ?', (month_start,))
    month_rev = c.fetchone()[0]

    c.execute('SELECT COALESCE(SUM(amount),0) FROM finances WHERE type="expense" AND date >= ?', (month_start,))
    month_exp = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (session['user_id'],))
    notif_count = c.fetchone()[0]

    c.execute('SELECT * FROM invoices ORDER BY created_at DESC LIMIT 5')
    recent = c.fetchall()
    conn.close()

    return render_template('dashboard.html',
        today_count=today_count, today_total=today_total,
        month_count=month_count, month_total=month_total,
        month_rev=month_rev, month_exp=month_exp,
        profit=month_rev - month_exp,
        recent_invoices=recent)

# ============================================================
# ROUTES - INVOICES
# ============================================================
@app.route('/invoices')
@login_required
def invoices():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    conn = get_db()
    c = conn.cursor()

    query = 'SELECT * FROM invoices WHERE 1=1'
    params = []
    if date_from:
        query += ' AND date >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND date <= ?'
        params.append(date_to)
    query += ' ORDER BY date DESC, id DESC'

    c.execute(query, params)
    invoices_list = c.fetchall()
    conn.close()

    return render_template('invoices.html', invoices=invoices_list,
                         date_from=date_from, date_to=date_to)

@app.route('/invoice/new', methods=['GET', 'POST'])
@login_required
def new_invoice():
    if request.method == 'POST':
        items_json = request.form.get('items_data', '[]')
        subtotal = float(request.form.get('subtotal', 0) or 0)
        discount = float(request.form.get('discount_percent', 0) or 0)
        tax = float(request.form.get('tax_percent', 0) or 0)
        total = subtotal * (1 - discount/100) * (1 + tax/100)

        # Image
        image_data = ''
        if 'invoice_image' in request.files:
            file = request.files['invoice_image']
            if file and file.filename:
                img_bytes = file.read()
                image_data = base64.b64encode(img_bytes).decode('utf-8')

        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO invoices
            (invoice_number, date, store_name, items, subtotal, discount_percent,
             tax_percent, total, notes, image_data, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (request.form.get('invoice_number'),
             request.form.get('invoice_date'),
             request.form.get('store_name'),
             items_json, subtotal, discount, tax, total,
             request.form.get('notes', ''),
             image_data,
             session['username']))
        invoice_id = c.lastrowid
        conn.commit()
        conn.close()

        flash('Tao hoa don thanh cong!', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM invoices')
    count = c.fetchone()[0]
    conn.close()
    invoice_number = f"HD{datetime.date.today().strftime('%Y%m%d')}{count+1:04d}"

    return render_template('invoice_form.html',
        invoice={'invoice_number': invoice_number,
                 'date': datetime.date.today().strftime('%Y-%m-%d')})

# Nhap text xuat hang loat
@app.route('/invoice/import-text', methods=['GET', 'POST'])
@login_required
def import_text():
    if request.method == 'POST':
        text = request.form.get('text_data', '')
        invoice_date = request.form.get('invoice_date', datetime.date.today().strftime('%Y-%m-%d'))
        store_name = request.form.get('store_name', '')
        num_cols = int(request.form.get('num_cols', 4) or 4)

        items = []
        grand_total = 0

        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip total line
            lower_line = line.lower()
            if 'tong' in lower_line or 'thanh tien' in lower_line or 'total' in lower_line:
                continue

            # Split by |
            parts = None
            if '\t' in line:
                parts = [p.strip() for p in line.split('\t') if p.strip()]
            elif '|' in line:
                parts = [p.strip() for p in line.split('|') if p.strip()]
            else:
                # Try to find last number in line
                tokens = line.split()
                try:
                    price = float(tokens[-1].replace(',', '').replace('.', ''))
                    name = ' '.join(tokens[:-1]).strip()
                    parts = [name, '1', str(price), str(price)]
                except:
                    pass

            if parts and len(parts) >= 2:
                name = parts[0].strip()
                if not name:
                    continue

                if num_cols == 2:
                    # Ten | Gia (so luong = 1)
                    qty = 1
                    price = float(parts[1].replace(',', ''))
                else:
                    # Ten | SoLuong | DonGia [ | ThanhTien]
                    try:
                        qty = float(parts[1].replace(',', ''))
                    except:
                        qty = 1
                    try:
                        price = float(parts[2].replace(',', ''))
                    except:
                        price = 0

                total = qty * price
                items.append({
                    'name': name,
                    'quantity': qty,
                    'price': price,
                    'total': total
                })
                grand_total += total

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM invoices')
        count = c.fetchone()[0]
        invoice_number = f"HD{datetime.date.today().strftime('%Y%m%d')}{count+1:04d}"

        c.execute('''INSERT INTO invoices
            (invoice_number, date, store_name, items, subtotal, total, notes, created_by)
            VALUES (?,?,?,?,?,?,?,?)''',
            (invoice_number, invoice_date, store_name,
             json.dumps(items), grand_total, grand_total,
             f'Tu dong tao tu nhap text - {len(items)} san pham', session['username']))
        invoice_id = c.lastrowid
        conn.commit()
        conn.close()

        flash(f'Tao {len(items)} san pham thanh cong!', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

    return render_template('import_text.html',
        today_str=datetime.date.today().strftime('%Y-%m-%d'))

# Quet anh OCR
@app.route('/invoice/scan-image', methods=['GET', 'POST'])
@login_required
def scan_image():
    if request.method == 'POST':
        if 'invoice_image' not in request.files:
            flash('Vui long upload anh!', 'danger')
            return redirect(request.url)

        file = request.files['invoice_image']
        if not file.filename:
            flash('Vui long upload anh!', 'danger')
            return redirect(request.url)

        img_bytes = file.read()
        image_data = base64.b64encode(img_bytes).decode('utf-8')

        # Try OCR
        extracted_text = ''
        if HAS_OCR:
            try:
                nparr = BytesIO(img_bytes)
                img_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img_array is not None:
                    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
                    extracted_text = pytesseract.image_to_string(gray, lang='vie+eng')
            except Exception as e:
                extracted_text = f'[OCR loi: {str(e)}]'
        else:
            extracted_text = '[OCR khong ho tro - vui long cai dat pytesseract va opencv]'

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM invoices')
        count = c.fetchone()[0]
        conn.close()

        invoice_number = f"HD{datetime.date.today().strftime('%Y%m%d')}{count+1:04d}"

        return render_template('scan_result.html',
            invoice_number=invoice_number,
            image_data=image_data,
            extracted_text=extracted_text)

    return render_template('scan_image.html')

# Gui anh cho admin
@app.route('/invoice/<int:invoice_id>/send-to-admin', methods=['POST'])
@login_required
def send_to_admin(invoice_id):
    message = request.form.get('message', '')
    image_data = request.form.get('image_data', '')

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE role = "admin"')
    admin = c.fetchone()
    if admin:
        c.execute('''INSERT INTO notifications
            (user_id, message, invoice_id, is_read)
            VALUES (?,?,?,0)''',
            (admin['id'], message, invoice_id))
        conn.commit()
        flash('Da gui anh cho admin!', 'success')
    else:
        flash('Khong tim thay admin!', 'danger')
    conn.close()

    return redirect(url_for('invoices'))

@app.route('/notifications')
@login_required
def notifications():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT * FROM notifications
        WHERE user_id = ? ORDER BY created_at DESC LIMIT 50''',
        (session['user_id'],))
    notifs = c.fetchall()
    c.execute('UPDATE notifications SET is_read=1 WHERE user_id=?', (session['user_id'],))
    conn.commit()
    conn.close()
    return render_template('notifications.html', notifications=notifs)

@app.route('/invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        flash('Khong tim thay hoa don!', 'danger')
        return redirect(url_for('invoices'))

    return render_template('invoice_view.html', invoice=invoice)

# Xuat Excel 1 hoa don chi tiet
@app.route('/invoice/<int:invoice_id>/export')
@login_required
def export_single_invoice(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        flash('Khong tim thay hoa don!', 'danger')
        return redirect(url_for('invoices'))

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoa Don"

    # Header
    ws['A1'] = 'HOA DON BAN HANG'
    ws['A1'].font = Font(bold=True, size=18, color='FFFFFF')
    ws['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells('A1:E1')
    ws.row_dimensions[1].height = 35

    # Info
    ws['A3'] = 'So hoa don:'
    ws['A3'].font = Font(bold=True)
    ws['B3'] = invoice['invoice_number']

    ws['A4'] = 'Ngay:'
    ws['A4'].font = Font(bold=True)
    ws['B4'] = invoice['date']

    ws['D3'] = 'Cua hang:'
    ws['D3'].font = Font(bold=True)
    ws.merge_cells('D3:D3')
    ws['E3'] = invoice['store_name'] or ''

    ws['D4'] = 'Nguoi tao:'
    ws['D4'].font = Font(bold=True)
    ws['E4'] = invoice['created_by']

    # Table header
    row = 6
    headers = ['STT', 'Ten Hang Hoa', 'So Luong', 'Don Gia', 'Thanh Tien']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
    ws.row_dimensions[row].height = 25

    # Items
    import json as _json
    try:
        items = _json.loads(invoice['items']) if invoice['items'] else []
    except:
        items = []

    row = 7
    stt = 1
    for item in items:
        ws.cell(row=row, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=2, value=item.get('name', ''))
        ws.cell(row=row, column=3, value=item.get('quantity', 1)).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=4, value=item.get('price', 0))
        ws.cell(row=row, column=4).number_format = '#,##0'
        ws.cell(row=row, column=5, value=item.get('total', 0))
        ws.cell(row=row, column=5).number_format = '#,##0'
        for col in range(1, 6):
            ws.cell(row=row, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
        row += 1
        stt += 1

    # Discount & Tax row
    if invoice['discount_percent'] > 0 or invoice['tax_percent'] > 0:
        if invoice['discount_percent'] > 0:
            disc_amt = invoice['subtotal'] * invoice['discount_percent'] / 100
            ws.cell(row=row, column=4, value=f'Giam gia ({invoice["discount_percent"]}%)')
            ws.cell(row=row, column=5, value=-disc_amt)
            ws.cell(row=row, column=5).number_format = '#,##0'
            for col in range(1, 6):
                ws.cell(row=row, column=col).border = Border(
                    left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin')
                )
            row += 1

        if invoice['tax_percent'] > 0:
            after_disc = invoice['subtotal'] * (1 - invoice['discount_percent']/100)
            tax_amt = after_disc * invoice['tax_percent'] / 100
            ws.cell(row=row, column=4, value=f'Thue ({invoice["tax_percent"]}%)')
            ws.cell(row=row, column=5, value=tax_amt)
            ws.cell(row=row, column=5).number_format = '#,##0'
            for col in range(1, 6):
                ws.cell(row=row, column=col).border = Border(
                    left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin')
                )
            row += 1

    # Total
    row += 1
    ws.cell(row=row, column=3, value='TONG CONG')
    ws.cell(row=row, column=3).font = Font(bold=True, size=12)
    ws.cell(row=row, column=5, value=invoice['total'])
    ws.cell(row=row, column=5).number_format = '#,##0'
    ws.cell(row=row, column=5).font = Font(bold=True, size=14, color='107C10')
    for col in range(1, 6):
        ws.cell(row=row, column=col).fill = PatternFill(
            start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')
        ws.cell(row=row, column=col).border = Border(
            left=Side(style='medium'), right=Side(style='medium'),
            top=Side(style='medium'), bottom=Side(style='medium')
        )

    # Ghi chu
    if invoice['notes']:
        row += 2
        ws.cell(row=row, column=1, value='Ghi chu:')
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2, value=invoice['notes'])
        ws.merge_cells(f'B{row}:E{row}')

    # Column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 18

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
        download_name=f'HoaDon_{invoice["invoice_number"]}.xlsx',
        as_attachment=True)

@app.route('/invoice/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
    invoice = c.fetchone()
    conn.close()

    if not invoice:
        flash('Khong tim thay hoa don!', 'danger')
        return redirect(url_for('invoices'))

    if request.method == 'POST':
        items_json = request.form.get('items_data', '[]')
        subtotal = float(request.form.get('subtotal', 0) or 0)
        discount = float(request.form.get('discount_percent', 0) or 0)
        tax = float(request.form.get('tax_percent', 0) or 0)
        total = subtotal * (1 - discount/100) * (1 + tax/100)

        image_data = invoice['image_data']
        if 'invoice_image' in request.files:
            file = request.files['invoice_image']
            if file and file.filename:
                img_bytes = file.read()
                image_data = base64.b64encode(img_bytes).decode('utf-8')

        conn = get_db()
        c = conn.cursor()
        c.execute('''UPDATE invoices SET
            invoice_number=?, date=?, store_name=?, items=?,
            subtotal=?, discount_percent=?, tax_percent=?, total=?,
            notes=?, image_data=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?''',
            (request.form.get('invoice_number'),
             request.form.get('invoice_date'),
             request.form.get('store_name'),
             items_json, subtotal, discount, tax, total,
             request.form.get('notes', ''),
             image_data,
             invoice_id))
        conn.commit()
        conn.close()

        flash('Cap nhat thanh cong!', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

    return render_template('invoice_form.html', invoice=invoice)

@app.route('/invoice/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
    conn.commit()
    conn.close()
    flash('Xoa thanh cong!', 'success')
    return redirect(url_for('invoices'))

# ============================================================
# ROUTES - FINANCE
# ============================================================
@app.route('/finance')
@login_required
def finance():
    month = request.args.get('month', datetime.date.today().strftime('%Y-%m'))

    conn = get_db()
    c = conn.cursor()

    c.execute('''SELECT * FROM finances WHERE type='revenue' AND date LIKE ?
        ORDER BY date DESC''', (f'{month}%',))
    revenues = c.fetchall()

    c.execute('''SELECT * FROM finances WHERE type='expense' AND date LIKE ?
        ORDER BY date DESC''', (f'{month}%',))
    expenses = c.fetchall()

    total_rev = sum(r['amount'] for r in revenues)
    total_exp = sum(e['amount'] for e in expenses)

    conn.close()

    return render_template('finance.html',
        revenues=revenues, expenses=expenses,
        total_rev=total_rev, total_exp=total_exp,
        profit=total_rev - total_exp, month=month)

@app.route('/finance/add', methods=['POST'])
@login_required
def finance_add():
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO finances
        (type, date, amount, category, reason, description, created_by)
        VALUES (?,?,?,?,?,?,?)''',
        (request.form.get('type'),
         request.form.get('date'),
         float(request.form.get('amount', 0) or 0),
         request.form.get('category', ''),
         request.form.get('reason', ''),
         request.form.get('description', ''),
         session['username']))
    conn.commit()
    conn.close()
    flash('Them giao dich thanh cong!', 'success')
    return redirect(url_for('finance'))

@app.route('/finance/delete/<int:finance_id>', methods=['POST'])
@login_required
def finance_delete(finance_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM finances WHERE id = ?', (finance_id,))
    conn.commit()
    conn.close()
    flash('Xoa thanh cong!', 'success')
    return redirect(url_for('finance'))

# ============================================================
# ROUTES - REPORT
# ============================================================
@app.route('/report')
@login_required
def report():
    date_from = request.args.get('date_from', datetime.date.today().replace(day=1).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', datetime.date.today().strftime('%Y-%m-%d'))
    month = request.args.get('month', '')

    conn = get_db()
    c = conn.cursor()

    if month:
        date_from = f'{month}-01'
        date_to = f'{month}-31'

    c.execute('''SELECT * FROM invoices WHERE date >= ? AND date <= ?
        ORDER BY date DESC''', (date_from, date_to))
    invoices_list = c.fetchall()

    c.execute('''SELECT * FROM finances WHERE date >= ? AND date <= ?
        ORDER BY date DESC''', (date_from, date_to))
    finances = c.fetchall()

    total_inv = sum(i['total'] for i in invoices_list)
    total_rev = sum(f['amount'] for f in finances if f['type'] == 'revenue')
    total_exp = sum(f['amount'] for f in finances if f['type'] == 'expense')

    conn.close()

    return render_template('report.html',
        invoices=invoices_list, finances=finances,
        date_from=date_from, date_to=date_to, month=month,
        total_inv=total_inv, total_rev=total_rev,
        total_exp=total_exp, profit=total_rev - total_exp)

# ============================================================
# EXPORT INVOICES EXCEL
# ============================================================
@app.route('/invoices/export')
@login_required
def export_invoices():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoa Don"

    title = 'DANH SACH HOA DON'
    if date_from and date_to:
        title = f'DANH SACH HOA DON - TU {date_from} DEN {date_to}'

    ws['A1'] = title
    ws['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells('A1:G1')
    ws.row_dimensions[1].height = 35

    headers = ['STT', 'So HD', 'Ngay', 'Cua Hang', 'Tong Tien', 'Ghi Chu', 'Nguoi Tao']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                           top=Side(style='thin'), bottom=Side(style='thin'))

    conn = get_db()
    c = conn.cursor()
    query = 'SELECT invoice_number, date, store_name, total, notes, created_by FROM invoices WHERE 1=1'
    params = []
    if date_from:
        query += ' AND date >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND date <= ?'
        params.append(date_to)
    query += ' ORDER BY date DESC'

    c.execute(query, params)
    row_num = 3
    stt = 1
    grand_total = 0

    for inv in c.fetchall():
        ws.cell(row=row_num, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=2, value=inv[0])
        ws.cell(row=row_num, column=3, value=inv[1])
        ws.cell(row=row_num, column=4, value=inv[2] or '')
        ws.cell(row=row_num, column=5, value=inv[3])
        ws.cell(row=row_num, column=5).number_format = '#,##0'
        ws.cell(row=row_num, column=6, value=inv[4] or '')
        ws.cell(row=row_num, column=7, value=inv[5])
        for col in range(1, 8):
            ws.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        grand_total += float(inv[3] or 0)
        row_num += 1
        stt += 1

    # Total row
    ws.cell(row=row_num, column=1, value='TONG CONG').font = Font(bold=True, color='FFFFFF')
    ws.cell(row=row_num, column=5, value=grand_total)
    ws.cell(row=row_num, column=5).number_format = '#,##0'
    ws.cell(row=row_num, column=5).font = Font(bold=True, color='FFFFFF')
    for col in range(1, 8):
        ws.cell(row=row_num, column=col).fill = PatternFill(
            start_color='0078D4', end_color='0078D4', fill_type='solid')
        ws.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'))

    conn.close()

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 14
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 15

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'DanhSachHoaDon_{date_from or "all"}_{date_to or "all"}.xlsx'
    return send_file(output, download_name=filename, as_attachment=True)

# ============================================================
# EXPORT FINANCE EXCEL
# ============================================================
@app.route('/finance/export')
@login_required
def export_finance():
    month = request.args.get('month', datetime.date.today().strftime('%Y-%m'))

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()

    conn = get_db()
    c = conn.cursor()

    # ===================== SHEET 1: DOANH THU =====================
    ws_rev = wb.active
    ws_rev.title = "1-Doanh Thu"
    ws_rev['A1'] = f'DOANH THU THANG {month}'
    ws_rev['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws_rev['A1'].fill = PatternFill(start_color='107C10', end_color='107C10', fill_type='solid')
    ws_rev['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws_rev.merge_cells('A1:E1')
    ws_rev.row_dimensions[1].height = 35

    for i, h in enumerate(['STT', 'Ngay', 'Loai', 'So Tien', 'Mo Ta'], 1):
        cell = ws_rev.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='107C10', end_color='107C10', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))

    c.execute('''SELECT date, category, amount, description FROM finances
        WHERE type='revenue' AND date LIKE ? ORDER BY date DESC''', (f'{month}%',))

    row_num = 3
    stt = 1
    total_rev = 0

    for rev in c.fetchall():
        ws_rev.cell(row=row_num, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws_rev.cell(row=row_num, column=2, value=rev[0])
        ws_rev.cell(row=row_num, column=3, value=rev[1] or '')
        ws_rev.cell(row=row_num, column=4, value=rev[2])
        ws_rev.cell(row=row_num, column=4).number_format = '#,##0'
        ws_rev.cell(row=row_num, column=5, value=rev[3] or '')
        for col in range(1, 6):
            ws_rev.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        total_rev += float(rev[2] or 0)
        row_num += 1
        stt += 1

    ws_rev.cell(row=row_num, column=1, value='TONG DOANH THU').font = Font(bold=True, color='FFFFFF')
    ws_rev.cell(row=row_num, column=4, value=total_rev)
    ws_rev.cell(row=row_num, column=4).number_format = '#,##0'
    ws_rev.cell(row=row_num, column=4).font = Font(bold=True, color='FFFFFF')
    for col in range(1, 6):
        ws_rev.cell(row=row_num, column=col).fill = PatternFill(
            start_color='107C10', end_color='107C10', fill_type='solid')
        ws_rev.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'))

    ws_rev.column_dimensions['A'].width = 8
    ws_rev.column_dimensions['B'].width = 14
    ws_rev.column_dimensions['C'].width = 20
    ws_rev.column_dimensions['D'].width = 18
    ws_rev.column_dimensions['E'].width = 30

    # ===================== SHEET 2: CHI PHI (CO LY DO) =====================
    ws_exp = wb.create_sheet("2-Chi Phi")
    ws_exp['A1'] = f'CHI PHI THANG {month}'
    ws_exp['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws_exp['A1'].fill = PatternFill(start_color='D13438', end_color='D13438', fill_type='solid')
    ws_exp['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws_exp.merge_cells('A1:F1')
    ws_exp.row_dimensions[1].height = 35

    for i, h in enumerate(['STT', 'Ngay', 'Loai Chi Phi', 'So Tien', 'Ly Do Chi (Chi Nhung Gi?)', 'Mo Ta'], 1):
        cell = ws_exp.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='D13438', end_color='D13438', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))

    c.execute('''SELECT date, category, amount, reason, description FROM finances
        WHERE type='expense' AND date LIKE ? ORDER BY date DESC''', (f'{month}%',))

    row_num = 3
    stt = 1
    total_exp = 0

    for exp in c.fetchall():
        ws_exp.cell(row=row_num, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws_exp.cell(row=row_num, column=2, value=exp[0])
        ws_exp.cell(row=row_num, column=3, value=exp[1] or '')
        ws_exp.cell(row=row_num, column=4, value=exp[2])
        ws_exp.cell(row=row_num, column=4).number_format = '#,##0'
        ws_exp.cell(row=row_num, column=5, value=exp[3] or '')
        ws_exp.cell(row=row_num, column=6, value=exp[4] or '')
        for col in range(1, 7):
            ws_exp.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        total_exp += float(exp[2] or 0)
        row_num += 1
        stt += 1

    ws_exp.cell(row=row_num, column=1, value='TONG CHI PHI').font = Font(bold=True, color='FFFFFF')
    ws_exp.cell(row=row_num, column=4, value=total_exp)
    ws_exp.cell(row=row_num, column=4).number_format = '#,##0'
    ws_exp.cell(row=row_num, column=4).font = Font(bold=True, color='FFFFFF')
    for col in range(1, 7):
        ws_exp.cell(row=row_num, column=col).fill = PatternFill(
            start_color='D13438', end_color='D13438', fill_type='solid')
        ws_exp.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'))

    ws_exp.column_dimensions['A'].width = 8
    ws_exp.column_dimensions['B'].width = 14
    ws_exp.column_dimensions['C'].width = 18
    ws_exp.column_dimensions['D'].width = 18
    ws_exp.column_dimensions['E'].width = 30
    ws_exp.column_dimensions['F'].width = 30

    # ===================== SHEET 3: TONG HOP =====================
    ws_sum = wb.create_sheet("3-Tong Hop")
    ws_sum['A1'] = f'TONG HOP TAI CHINH THANG {month}'
    ws_sum['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws_sum['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws_sum['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws_sum.merge_cells('A1:B1')
    ws_sum.row_dimensions[1].height = 35

    loi = total_rev - total_exp
    data = [
        ['CHI TIEU', 'SO TIEN'],
        ['Tong Doanh Thu (Thu)', total_rev],
        ['Tong Chi Phi (Chi)', total_exp],
        ['LOI NHUAN (Thu - Chi)', loi],
    ]

    for r, row_data in enumerate(data, 2):
        ws_sum.cell(row=r, column=1, value=row_data[0])
        ws_sum.cell(row=r, column=2, value=row_data[1])
        ws_sum.cell(row=r, column=2).number_format = '#,##0'

        if r == 2:
            ws_sum.cell(row=r, column=1).font = Font(bold=True, color='FFFFFF')
            ws_sum.cell(row=r, column=2).font = Font(bold=True, color='FFFFFF')
            ws_sum.cell(row=r, column=1).fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
            ws_sum.cell(row=r, column=2).fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        elif r == 3:
            ws_sum.cell(row=r, column=1).font = Font(bold=True, color='107C10')
            ws_sum.cell(row=r, column=2).font = Font(bold=True, color='107C10')
        elif r == 4:
            ws_sum.cell(row=r, column=1).font = Font(bold=True, color='D13438')
            ws_sum.cell(row=r, column=2).font = Font(bold=True, color='D13438')
        elif r == 5:
            color = '107C10' if loi >= 0 else 'D13438'
            bg = 'E8F5E9' if loi >= 0 else 'FFEBEE'
            ws_sum.cell(row=r, column=1).font = Font(bold=True, size=14)
            ws_sum.cell(row=r, column=2).font = Font(bold=True, size=14, color=color)
            ws_sum.cell(row=r, column=1).fill = PatternFill(start_color=bg, end_color=bg, fill_type='solid')
            ws_sum.cell(row=r, column=2).fill = PatternFill(start_color=bg, end_color=bg, fill_type='solid')

        for col in range(1, 3):
            ws_sum.cell(row=r, column=col).border = Border(
                left=Side(style='medium'), right=Side(style='medium'),
                top=Side(style='medium'), bottom=Side(style='medium'))
            ws_sum.cell(row=r, column=col).alignment = Alignment(
                horizontal='left' if col == 1 else 'right',
                vertical='center')
            ws_sum.row_dimensions[r].height = 25

    ws_sum.column_dimensions['A'].width = 35
    ws_sum.column_dimensions['B'].width = 20

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, download_name=f'TaiChinh_{month}.xlsx', as_attachment=True)

# ============================================================
# EXPORT REPORT EXCEL
# ============================================================
@app.route('/report/export')
@login_required
def report_export():
    date_from = request.args.get('date_from', datetime.date.today().replace(day=1).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', datetime.date.today().strftime('%Y-%m-%d'))
    month = request.args.get('month', '')

    if month:
        date_from = f'{month}-01'
        date_to = f'{month}-31'

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    conn = get_db()
    c = conn.cursor()

    # SHEET 1: HOA DON
    ws = wb.active
    ws.title = "1-Hoa Don"
    title = f'BAO CAO HOA DON - TU {date_from} DEN {date_to}'
    ws['A1'] = title
    ws['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells('A1:G1')
    ws.row_dimensions[1].height = 35

    headers = ['STT', 'So HD', 'Ngay', 'Cua Hang', 'Tong Tien', 'Ghi Chu', 'Nguoi Tao']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))

    c.execute('''SELECT invoice_number, date, store_name, total, notes, created_by
        FROM invoices WHERE date >= ? AND date <= ? ORDER BY date DESC''',
        (date_from, date_to))

    row_num = 3
    stt = 1
    grand_total = 0

    for inv in c.fetchall():
        ws.cell(row=row_num, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=2, value=inv[0])
        ws.cell(row=row_num, column=3, value=inv[1])
        ws.cell(row=row_num, column=4, value=inv[2] or '')
        ws.cell(row=row_num, column=5, value=inv[3])
        ws.cell(row=row_num, column=5).number_format = '#,##0'
        ws.cell(row=row_num, column=6, value=inv[4] or '')
        ws.cell(row=row_num, column=7, value=inv[5])
        for col in range(1, 8):
            ws.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        grand_total += float(inv[3] or 0)
        row_num += 1
        stt += 1

    ws.cell(row=row_num, column=1, value='TONG CONG HOA DON').font = Font(bold=True, color='FFFFFF')
    ws.cell(row=row_num, column=5, value=grand_total)
    ws.cell(row=row_num, column=5).number_format = '#,##0'
    ws.cell(row=row_num, column=5).font = Font(bold=True, color='FFFFFF')
    for col in range(1, 8):
        ws.cell(row=row_num, column=col).fill = PatternFill(
            start_color='0078D4', end_color='0078D4', fill_type='solid')
        ws.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'))

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 14
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 30
    ws.column_dimensions['G'].width = 15

    # SHEET 2: TAI CHINH
    ws2 = wb.create_sheet("2-Tai Chinh")

    ws2['A1'] = f'DOANH THU - TU {date_from} DEN {date_to}'
    ws2['A1'].font = Font(bold=True, size=14, color='FFFFFF')
    ws2['A1'].fill = PatternFill(start_color='107C10', end_color='107C10', fill_type='solid')
    ws2['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws2.merge_cells('A1:E1')
    ws2.row_dimensions[1].height = 30

    for i, h in enumerate(['STT', 'Ngay', 'Loai', 'So Tien', 'Mo Ta'], 1):
        cell = ws2.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='107C10', end_color='107C10', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))

    c.execute('''SELECT date, category, amount, description FROM finances
        WHERE type='revenue' AND date >= ? AND date <= ? ORDER BY date DESC''',
        (date_from, date_to))

    row_num = 3
    stt = 1
    total_rev = 0

    for rev in c.fetchall():
        ws2.cell(row=row_num, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws2.cell(row=row_num, column=2, value=rev[0])
        ws2.cell(row=row_num, column=3, value=rev[1] or '')
        ws2.cell(row=row_num, column=4, value=rev[2])
        ws2.cell(row=row_num, column=4).number_format = '#,##0'
        ws2.cell(row=row_num, column=5, value=rev[3] or '')
        for col in range(1, 6):
            ws2.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        total_rev += float(rev[2] or 0)
        row_num += 1
        stt += 1

    row_num += 1
    ws2.cell(row=row_num, column=1, value='CHI PHI').font = Font(bold=True, size=13, color='FFFFFF')
    ws2.cell(row=row_num, column=1).fill = PatternFill(start_color='D13438', end_color='D13438', fill_type='solid')
    ws2.merge_cells(f'A{row_num}:E{row_num}')
    ws2.row_dimensions[row_num].height = 25

    row_num += 1
    for i, h in enumerate(['STT', 'Ngay', 'Loai Chi Phi', 'So Tien', 'Ly Do'], 1):
        cell = ws2.cell(row=row_num, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='D13438', end_color='D13438', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))

    c.execute('''SELECT date, category, amount, reason FROM finances
        WHERE type='expense' AND date >= ? AND date <= ? ORDER BY date DESC''',
        (date_from, date_to))

    row_num += 1
    stt = 1
    total_exp = 0

    for exp in c.fetchall():
        ws2.cell(row=row_num, column=1, value=stt).alignment = Alignment(horizontal='center')
        ws2.cell(row=row_num, column=2, value=exp[0])
        ws2.cell(row=row_num, column=3, value=exp[1] or '')
        ws2.cell(row=row_num, column=4, value=exp[2])
        ws2.cell(row=row_num, column=4).number_format = '#,##0'
        ws2.cell(row=row_num, column=5, value=exp[3] or '')
        for col in range(1, 6):
            ws2.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        total_exp += float(exp[2] or 0)
        row_num += 1
        stt += 1

    ws2.column_dimensions['A'].width = 8
    ws2.column_dimensions['B'].width = 14
    ws2.column_dimensions['C'].width = 20
    ws2.column_dimensions['D'].width = 18
    ws2.column_dimensions['E'].width = 30

    # SHEET 3: TONG HOP
    ws3 = wb.create_sheet("3-Tong Hop")
    ws3['A1'] = f'TONG HOP BAO CAO - TU {date_from} DEN {date_to}'
    ws3['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws3['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws3['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws3.merge_cells('A1:B1')
    ws3.row_dimensions[1].height = 35

    loi = total_rev - total_exp
    data = [
        ['CHI TIEU', 'SO TIEN'],
        ['Tong Hoa Don', grand_total],
        ['Tong Doanh Thu (Thu)', total_rev],
        ['Tong Chi Phi (Chi)', total_exp],
        ['LOI NHUAN', loi],
    ]

    for r, row_data in enumerate(data, 2):
        ws3.cell(row=r, column=1, value=row_data[0])
        ws3.cell(row=r, column=2, value=row_data[1])
        ws3.cell(row=r, column=2).number_format = '#,##0'

        if r == 2:
            ws3.cell(row=r, column=1).font = Font(bold=True, color='FFFFFF')
            ws3.cell(row=r, column=2).font = Font(bold=True, color='FFFFFF')
            ws3.cell(row=r, column=1).fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
            ws3.cell(row=r, column=2).fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        elif r == 3:
            ws3.cell(row=r, column=1).font = Font(bold=True, color='0078D4')
            ws3.cell(row=r, column=2).font = Font(bold=True, color='0078D4')
        elif r == 4:
            ws3.cell(row=r, column=1).font = Font(bold=True, color='107C10')
            ws3.cell(row=r, column=2).font = Font(bold=True, color='107C10')
        elif r == 5:
            ws3.cell(row=r, column=1).font = Font(bold=True, color='D13438')
            ws3.cell(row=r, column=2).font = Font(bold=True, color='D13438')
        elif r == 6:
            color = '107C10' if loi >= 0 else 'D13438'
            bg = 'E8F5E9' if loi >= 0 else 'FFEBEE'
            ws3.cell(row=r, column=1).font = Font(bold=True, size=14)
            ws3.cell(row=r, column=2).font = Font(bold=True, size=14, color=color)
            ws3.cell(row=r, column=1).fill = PatternFill(start_color=bg, end_color=bg, fill_type='solid')
            ws3.cell(row=r, column=2).fill = PatternFill(start_color=bg, end_color=bg, fill_type='solid')

        for col in range(1, 3):
            ws3.cell(row=r, column=col).border = Border(
                left=Side(style='medium'), right=Side(style='medium'),
                top=Side(style='medium'), bottom=Side(style='medium'))
            ws3.cell(row=r, column=col).alignment = Alignment(
                horizontal='left' if col == 1 else 'right', vertical='center')
            ws3.row_dimensions[r].height = 25

    ws3.column_dimensions['A'].width = 30
    ws3.column_dimensions['B'].width = 20

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
        download_name=f'BaoCao_{date_from}_{date_to}.xlsx',
        as_attachment=True)

# ============================================================
# USERS
# ============================================================
@app.route('/users')
@admin_required
def users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, role, created_at FROM users ORDER BY created_at')
    users_list = c.fetchall()
    conn.close()
    return render_template('users.html', users=users_list)

@app.route('/users/add', methods=['POST'])
@admin_required
def users_add():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'ketoan')

    if not username or not password:
        flash('Vui long dien day du!', 'danger')
        return redirect(url_for('users'))

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
    if c.fetchone()[0] > 0:
        flash('Ten dang nhap da ton tai!', 'danger')
        conn.close()
        return redirect(url_for('users'))

    c.execute('INSERT INTO users (username, password, role) VALUES (?,?,?)',
              (username, generate_password_hash(password), role))
    conn.commit()
    conn.close()
    flash(f'Tao tai khoan {username} thanh cong!', 'success')
    return redirect(url_for('users'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def users_delete(user_id):
    if user_id == session['user_id']:
        flash('Khong the xoa chinh minh!', 'danger')
        return redirect(url_for('users'))

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Xoa thanh cong!', 'success')
    return redirect(url_for('users'))

# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# ============================================================
# MAIN
# ============================================================
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
