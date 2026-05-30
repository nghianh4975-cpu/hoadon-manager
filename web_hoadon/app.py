# -*- coding: utf-8 -*-
"""
HOA DON WEB APP - Flask Application
Deploy len Render.com Free
"""

import os
import sqlite3
import uuid
import datetime
from functools import wraps
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# APP CONFIG
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', str(uuid.uuid4()))

DATABASE = os.path.join(os.path.dirname(__file__), 'hoadon.db')

# Jinja2 custom filter
@app.template_filter('from_json')
def from_json(value):
    import json
    try:
        return json.loads(value)
    except:
        return []

# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'ketoan',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
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
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            reason TEXT,
            description TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        ''', ('admin', generate_password_hash('admin123'), 'admin'))

    conn.commit()
    conn.close()

# ============================================================
# AUTH DECORATOR
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Ban khong co quyen truy cap trang nay!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

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
            flash(f'Chao mui {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Ten dang nhap hoac mat khau khong dung!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Da dang xuat!', 'info')
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pass = request.form.get('current_password', '')
        new_pass = request.form.get('new_password', '')
        confirm_pass = request.form.get('confirm_password', '')

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE id = ?', (session['user_id'],))
        user = c.fetchone()

        if not check_password_hash(user['password'], current_pass):
            flash('Mat khau hien tai khong dung!', 'danger')
            conn.close()
            return render_template('change_password.html')

        if new_pass != confirm_pass:
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
    c.execute('SELECT COUNT(*), COALESCE(SUM(total), 0) FROM invoices WHERE date = ?', (today,))
    today_inv = c.fetchone()
    today_count = today_inv[0]
    today_total = today_inv[1]

    month_start = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
    c.execute('SELECT COUNT(*), COALESCE(SUM(total), 0) FROM invoices WHERE date >= ?', (month_start,))
    month_inv = c.fetchone()
    month_count = month_inv[0]
    month_total = month_inv[1]

    c.execute('SELECT COALESCE(SUM(amount), 0) FROM finances WHERE type = "revenue" AND date >= ?', (month_start,))
    month_rev = c.fetchone()[0]

    c.execute('SELECT COALESCE(SUM(amount), 0) FROM finances WHERE type = "expense" AND date >= ?', (month_start,))
    month_exp = c.fetchone()[0]

    c.execute('SELECT * FROM invoices ORDER BY created_at DESC LIMIT 5')
    recent_invoices = c.fetchall()

    conn.close()

    return render_template('dashboard.html',
                         today_count=today_count, today_total=today_total,
                         month_count=month_count, month_total=month_total,
                         month_rev=month_rev, month_exp=month_exp,
                         profit=month_rev - month_exp,
                         recent_invoices=recent_invoices)

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
        data = request.form
        items_json = data.get('items_data', '[]')
        subtotal = float(data.get('subtotal', 0))
        discount = float(data.get('discount_percent', 0))
        tax = float(data.get('tax_percent', 0))
        after_discount = subtotal * (1 - discount / 100)
        total = after_discount * (1 + tax / 100)

        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO invoices (invoice_number, date, store_name, items,
                                subtotal, discount_percent, tax_percent, total,
                                notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('invoice_number'),
            data.get('invoice_date'),
            data.get('store_name'),
            items_json,
            subtotal,
            discount,
            tax,
            total,
            data.get('notes'),
            session['username']
        ))
        conn.commit()
        invoice_id = c.lastrowid
        conn.close()

        flash('Tao hoa don thanh cong!', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM invoices')
    count = c.fetchone()[0]
    conn.close()

    invoice_number = f"HD{datetime.date.today().strftime('%Y%m%d')}{count + 1:04d}"

    return render_template('invoice_form.html', invoice={'invoice_number': invoice_number})

# Nhap text xuat Excel
@app.route('/invoice/import-text', methods=['GET', 'POST'])
@login_required
def import_text():
    if request.method == 'POST':
        text_data = request.form.get('text_data', '')
        lines = text_data.strip().split('\n')

        items = []
        subtotal = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                name = parts[0].strip()
                try:
                    price = float(parts[1].strip().replace(',', '').replace('.', ''))
                    items.append({'name': name, 'quantity': 1, 'price': price, 'total': price})
                    subtotal += price
                except:
                    pass
            elif '\t' not in line:
                try:
                    price = float(line.strip().replace(',', '').replace('.', ''))
                    items.append({'name': f'San pham {len(items)+1}', 'quantity': 1, 'price': price, 'total': price})
                    subtotal += price
                except:
                    pass

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM invoices')
        count = c.fetchone()[0]
        invoice_number = f"HD{datetime.date.today().strftime('%Y%m%d')}{count + 1:04d}"

        c.execute('''
            INSERT INTO invoices (invoice_number, date, store_name, items,
                                subtotal, discount_percent, tax_percent, total,
                                notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            invoice_number,
            datetime.date.today().strftime('%Y-%m-%d'),
            '',
            '[]',
            subtotal,
            0, 0, subtotal,
            'Tu dong tao tu nhap text',
            session['username']
        ))
        conn.commit()
        invoice_id = c.lastrowid
        conn.close()

        flash(f'Tao hoa don {invoice_number} tu text thanh cong!', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

    return render_template('import_text.html')

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
        data = request.form
        subtotal = float(data.get('subtotal', 0))
        discount = float(data.get('discount_percent', 0))
        tax = float(data.get('tax_percent', 0))
        after_discount = subtotal * (1 - discount / 100)
        total = after_discount * (1 + tax / 100)

        conn = get_db()
        c = conn.cursor()
        c.execute('''
            UPDATE invoices SET
                invoice_number = ?, date = ?, store_name = ?, items = ?,
                subtotal = ?, discount_percent = ?, tax_percent = ?, total = ?,
                notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data.get('invoice_number'),
            data.get('invoice_date'),
            data.get('store_name'),
            data.get('items_data'),
            subtotal, discount, tax, total,
            data.get('notes'),
            invoice_id
        ))
        conn.commit()
        conn.close()

        flash('Cap nhat hoa don thanh cong!', 'success')
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

    flash('Xoa hoa don thanh cong!', 'success')
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

    c.execute('''
        SELECT * FROM finances
        WHERE type = 'revenue' AND date LIKE ?
        ORDER BY date DESC
    ''', (f'{month}%',))
    revenues = c.fetchall()

    c.execute('''
        SELECT * FROM finances
        WHERE type = 'expense' AND date LIKE ?
        ORDER BY date DESC
    ''', (f'{month}%',))
    expenses = c.fetchall()

    total_rev = sum(r['amount'] for r in revenues)
    total_exp = sum(e['amount'] for e in expenses)

    conn.close()

    return render_template('finance.html',
                         revenues=revenues, expenses=expenses,
                         total_rev=total_rev, total_exp=total_exp,
                         profit=total_rev - total_exp,
                         month=month)

@app.route('/finance/add', methods=['POST'])
@login_required
def finance_add():
    data = request.form

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO finances (type, date, amount, category, reason, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('type'),
        data.get('date'),
        float(data.get('amount', 0)),
        data.get('category', ''),
        data.get('reason', ''),
        data.get('description', ''),
        session['username']
    ))
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

    flash('Xoa giao dich thanh cong!', 'success')
    return redirect(url_for('finance'))

# ============================================================
# ROUTES - REPORT
# ============================================================
@app.route('/report')
@login_required
def report():
    date_from = request.args.get('date_from', datetime.date.today().replace(day=1).strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', datetime.date.today().strftime('%Y-%m-%d'))

    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT * FROM invoices
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    ''', (date_from, date_to))
    invoices_list = c.fetchall()

    c.execute('''
        SELECT * FROM finances
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    ''', (date_from, date_to))
    finances = c.fetchall()

    total_inv = sum(i['total'] for i in invoices_list)
    total_rev = sum(f['amount'] for f in finances if f['type'] == 'revenue')
    total_exp = sum(f['amount'] for f in finances if f['type'] == 'expense')

    conn.close()

    return render_template('report.html',
                         invoices=invoices_list, finances=finances,
                         date_from=date_from, date_to=date_to,
                         total_inv=total_inv, total_rev=total_rev,
                         total_exp=total_exp, profit=total_rev - total_exp)

# ============================================================
# ROUTES - EXPORT INVOICES EXCEL
# ============================================================
@app.route('/invoices/export')
@login_required
def export_invoices():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        flash('Khong the xuat Excel.', 'danger')
        return redirect(url_for('invoices'))

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoa don"

    ws['A1'] = 'DANH SACH HOA DON'
    ws['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells('A1:F1')
    ws.row_dimensions[1].height = 30

    start_row = 2
    if date_from and date_to:
        ws['A2'] = f'Tu ngay: {date_from} - Den ngay: {date_to}'
        ws['A2'].font = Font(italic=True, size=11)
        ws.merge_cells('A2:F2')
        start_row = 3

    headers = ['STT', 'So HD', 'Ngay', 'Cua hang', 'Tong tien', 'Ghi chu']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    conn = get_db()
    c = conn.cursor()

    query = 'SELECT invoice_number, date, store_name, total, notes FROM invoices WHERE 1=1'
    params = []
    if date_from:
        query += ' AND date >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND date <= ?'
        params.append(date_to)
    query += ' ORDER BY date DESC'

    c.execute(query, params)
    row_num = start_row + 1
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
        for col in range(1, 7):
            ws.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
        grand_total += float(inv[3] or 0)
        row_num += 1
        stt += 1

    ws.cell(row=row_num, column=1, value='TONG CONG').font = Font(bold=True)
    ws.cell(row=row_num, column=5, value=grand_total)
    ws.cell(row=row_num, column=5).number_format = '#,##0'
    ws.cell(row=row_num, column=5).font = Font(bold=True)
    for col in range(1, 7):
        ws.cell(row=row_num, column=col).fill = PatternFill(
            start_color='E8F4FD', end_color='E8F4FD', fill_type='solid'
        )
        ws.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    conn.close()
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 14
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 30

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'hoadon_{date_from or "all"}_{date_to or "all"}.xlsx'
    return send_file(output, download_name=filename, as_attachment=True)

# ============================================================
# ROUTES - EXPORT FINANCE EXCEL
# ============================================================
@app.route('/finance/export')
@login_required
def export_finance():
    month = request.args.get('month', datetime.date.today().strftime('%Y-%m'))

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        flash('Khong the xuat Excel.', 'danger')
        return redirect(url_for('finance'))

    wb = Workbook()

    # Sheet 1: Doanh thu
    ws_rev = wb.active
    ws_rev.title = "Doanh thu"
    ws_rev['A1'] = f'DOANH THU THANG {month}'
    ws_rev['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws_rev['A1'].fill = PatternFill(start_color='107C10', end_color='107C10', fill_type='solid')
    ws_rev['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws_rev.merge_cells('A1:E1')
    ws_rev.row_dimensions[1].height = 30

    headers = ['STT', 'Ngay', 'Loai', 'So tien', 'Mo ta']
    for i, h in enumerate(headers, 1):
        cell = ws_rev.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='107C10', end_color='107C10', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT date, category, amount, description FROM finances
        WHERE type = 'revenue' AND date LIKE ?
        ORDER BY date DESC
    ''', (f'{month}%',))

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
                top=Side(style='thin'), bottom=Side(style='thin')
            )
        total_rev += float(rev[2] or 0)
        row_num += 1
        stt += 1

    ws_rev.cell(row=row_num, column=1, value='TONG DOANH THU').font = Font(bold=True)
    ws_rev.cell(row=row_num, column=4, value=total_rev)
    ws_rev.cell(row=row_num, column=4).number_format = '#,##0'
    ws_rev.cell(row=row_num, column=4).font = Font(bold=True, color='107C10')
    for col in range(1, 6):
        ws_rev.cell(row=row_num, column=col).fill = PatternFill(
            start_color='E8F5E9', end_color='E8F5E9', fill_type='solid'
        )
        ws_rev.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    # Sheet 2: Chi phi
    ws_exp = wb.create_sheet("Chi phi")
    ws_exp['A1'] = f'CHI PHI THANG {month}'
    ws_exp['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws_exp['A1'].fill = PatternFill(start_color='D13438', end_color='D13438', fill_type='solid')
    ws_exp['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws_exp.merge_cells('A1:F1')
    ws_exp.row_dimensions[1].height = 30

    headers = ['STT', 'Ngay', 'Loai', 'So tien', 'Ly do', 'Mo ta']
    for i, h in enumerate(headers, 1):
        cell = ws_exp.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='D13438', end_color='D13438', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    c.execute('''
        SELECT date, category, amount, reason, description FROM finances
        WHERE type = 'expense' AND date LIKE ?
        ORDER BY date DESC
    ''', (f'{month}%',))

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
                top=Side(style='thin'), bottom=Side(style='thin')
            )
        total_exp += float(exp[2] or 0)
        row_num += 1
        stt += 1

    ws_exp.cell(row=row_num, column=1, value='TONG CHI PHI').font = Font(bold=True)
    ws_exp.cell(row=row_num, column=4, value=total_exp)
    ws_exp.cell(row=row_num, column=4).number_format = '#,##0'
    ws_exp.cell(row=row_num, column=4).font = Font(bold=True, color='D13438')
    for col in range(1, 7):
        ws_exp.cell(row=row_num, column=col).fill = PatternFill(
            start_color='FFEBEE', end_color='FFEBEE', fill_type='solid'
        )
        ws_exp.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    # Sheet 3: Tong hop
    ws_sum = wb.create_sheet("Tong hop")
    ws_sum['A1'] = f'TONG HOP TAI CHINH THANG {month}'
    ws_sum['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws_sum['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws_sum['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws_sum.merge_cells('A1:B1')
    ws_sum.row_dimensions[1].height = 30

    loi = total_rev - total_exp
    data = [
        ['CHI TIEU', 'SO TIEN'],
        ['Tong doanh thu', total_rev],
        ['Tong chi phi', total_exp],
        ['Loi nhuan', loi],
    ]

    for r, row_data in enumerate(data, 2):
        ws_sum.cell(row=r, column=1, value=row_data[0])
        ws_sum.cell(row=r, column=2, value=row_data[1])
        ws_sum.cell(row=r, column=2).number_format = '#,##0'

        if r == 2:
            ws_sum.cell(row=r, column=1).font = Font(bold=True, color='FFFFFF')
            ws_sum.cell(row=r, column=2).font = Font(bold=True, color='FFFFFF')
            ws_sum.cell(row=r, column=1).fill = PatternFill(
                start_color='0078D4', end_color='0078D4', fill_type='solid'
            )
            ws_sum.cell(row=r, column=2).fill = PatternFill(
                start_color='0078D4', end_color='0078D4', fill_type='solid'
            )
        elif r == 5:
            ws_sum.cell(row=r, column=1).font = Font(bold=True, size=12)
            ws_sum.cell(row=r, column=2).font = Font(bold=True, size=12)
            color = '107C10' if loi >= 0 else 'D13438'
            bg = 'E8F5E9' if loi >= 0 else 'FFEBEE'
            ws_sum.cell(row=r, column=1).fill = PatternFill(start_color=bg, end_color=bg, fill_type='solid')
            ws_sum.cell(row=r, column=2).fill = PatternFill(start_color=bg, end_color=bg, fill_type='solid')
            ws_sum.cell(row=r, column=2).font = Font(bold=True, size=12, color=color)

        for col in range(1, 3):
            ws_sum.cell(row=r, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
            ws_sum.cell(row=r, column=col).alignment = Alignment(
                horizontal='left' if col == 1 else 'right'
            )

    ws_sum.column_dimensions['A'].width = 25
    ws_sum.column_dimensions['B'].width = 20
    ws_rev.column_dimensions['A'].width = 8
    ws_rev.column_dimensions['B'].width = 14
    ws_rev.column_dimensions['C'].width = 20
    ws_rev.column_dimensions['D'].width = 18
    ws_rev.column_dimensions['E'].width = 25
    ws_exp.column_dimensions['A'].width = 8
    ws_exp.column_dimensions['B'].width = 14
    ws_exp.column_dimensions['C'].width = 15
    ws_exp.column_dimensions['D'].width = 18
    ws_exp.column_dimensions['E'].width = 20
    ws_exp.column_dimensions['F'].width = 25

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'tai_chinh_{month}.xlsx'
    return send_file(output, download_name=filename, as_attachment=True)

# ============================================================
# ROUTES - REPORT EXPORT
# ============================================================
@app.route('/report/export')
@login_required
def report_export():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    except ImportError:
        flash('Khong the xuat Excel.', 'danger')
        return redirect(url_for('report'))

    wb = Workbook()

    # Sheet Hoa don
    ws = wb.active
    ws.title = "Hoa don"

    ws['A1'] = f'BAO CAO TU {date_from} DEN {date_to}'
    ws['A1'].font = Font(bold=True, size=16, color='FFFFFF')
    ws['A1'].fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.merge_cells('A1:F1')
    ws.row_dimensions[1].height = 30

    headers = ['STT', 'So HD', 'Ngay', 'Cua hang', 'Tong tien', 'Ghi chu']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=i, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
        cell.border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT invoice_number, date, store_name, total, notes FROM invoices
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    ''', (date_from, date_to))

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
        for col in range(1, 7):
            ws.cell(row=row_num, column=col).border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
        grand_total += float(inv[3] or 0)
        row_num += 1
        stt += 1

    ws.cell(row=row_num, column=1, value='TONG CONG').font = Font(bold=True)
    ws.cell(row=row_num, column=5, value=grand_total)
    ws.cell(row=row_num, column=5).number_format = '#,##0'
    ws.cell(row=row_num, column=5).font = Font(bold=True)
    for col in range(1, 7):
        ws.cell(row=row_num, column=col).fill = PatternFill(
            start_color='E8F4FD', end_color='E8F4FD', fill_type='solid'
        )
        ws.cell(row=row_num, column=col).border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 14
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 30

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'baocao_{date_from}_{date_to}.xlsx'
    return send_file(output, download_name=filename, as_attachment=True)

# ============================================================
# ROUTES - USER MANAGEMENT
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
        flash('Vui long dien day du thong tin!', 'danger')
        return redirect(url_for('users'))

    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
    if c.fetchone()[0] > 0:
        flash('Ten dang nhap da ton tai!', 'danger')
        conn.close()
        return redirect(url_for('users'))

    c.execute('''
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
    ''', (username, generate_password_hash(password), role))
    conn.commit()
    conn.close()

    flash(f'Tao tai khoan "{username}" thanh cong!', 'success')
    return redirect(url_for('users'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def users_delete(user_id):
    if user_id == session['user_id']:
        flash('Ban khong the xoa tai khoan cua chinh minh!', 'danger')
        return redirect(url_for('users'))

    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash('Xoa tai khoan thanh cong!', 'success')
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
