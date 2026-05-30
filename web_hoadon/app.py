# -*- coding: utf-8 -*-
"""
HOA DON WEB APP - Flask Application
Deploy lên Render.com Free
"""

import os
import sqlite3
import hashlib
import uuid
import datetime
from functools import wraps
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# APP CONFIG
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', str(uuid.uuid4()))

# Database
DATABASE = os.path.join(os.path.dirname(__file__), 'hoadon.db')

# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db():
    """Kết nối database SQLite"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo database"""
    conn = get_db()
    c = conn.cursor()
    
    # Bảng users
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'ketoan',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng hóa đơn
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
    
    # Bảng tài chính
    c.execute('''
        CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            description TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tạo tài khoản admin mặc định nếu chưa có
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
            flash('Bạn không có quyền truy cập trang này!', 'danger')
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
            flash(f'Chào mừng {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất!', 'info')
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
            flash('Mật khẩu hiện tại không đúng!', 'danger')
            conn.close()
            return render_template('change_password.html')
        
        if new_pass != confirm_pass:
            flash('Mật khẩu mới không khớp!', 'danger')
            conn.close()
            return render_template('change_password.html')
        
        c.execute('UPDATE users SET password = ? WHERE id = ?', 
                  (generate_password_hash(new_pass), session['user_id']))
        conn.commit()
        conn.close()
        
        flash('Đổi mật khẩu thành công!', 'success')
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
    
    # Thống kê hóa đơn hôm nay
    today = datetime.date.today().strftime('%Y-%m-%d')
    c.execute('SELECT COUNT(*), COALESCE(SUM(total), 0) FROM invoices WHERE date = ?', (today,))
    today_inv = c.fetchone()
    
    # Thống kê tháng này
    month_start = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
    c.execute('SELECT COUNT(*), COALESCE(SUM(total), 0) FROM invoices WHERE date >= ?', (month_start,))
    month_inv = c.fetchone()
    
    # Thống kê tài chính tháng
    c.execute('SELECT COALESCE(SUM(amount), 0) FROM finances WHERE type = "revenue" AND date >= ?', (month_start,))
    month_rev = c.fetchone()[0]
    
    c.execute('SELECT COALESCE(SUM(amount), 0) FROM finances WHERE type = "expense" AND date >= ?', (month_start,))
    month_exp = c.fetchone()[0]
    
    # Hóa đơn gần đây
    c.execute('SELECT * FROM invoices ORDER BY created_at DESC LIMIT 5')
    recent_invoices = c.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html',
                         today_count=today_inv[0], today_total=today_inv[1],
                         month_count=month_inv[0], month_total=month_inv[1],
                         month_rev=month_rev, month_exp=month_exp,
                         profit=month_rev - month_exp,
                         recent_invoices=recent_invoices)

# ============================================================
# ROUTES - INVOICES
# ============================================================
@app.route('/invoices')
@login_required
def invoices():
    # Lọc theo ngày
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
        
        # Parse items từ JSON
        items_json = data.get('items_data', '[]')
        
        # Tính tổng
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
        
        flash('Tạo hóa đơn thành công!', 'success')
        return redirect(url_for('view_invoice', invoice_id=invoice_id))
    
    # Tạo số hóa đơn mới
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM invoices')
    count = c.fetchone()[0]
    conn.close()
    
    invoice_number = f"HD{datetime.date.today().strftime('%Y%m%d')}{count + 1:04d}"
    
    return render_template('invoice_form.html', invoice={'invoice_number': invoice_number})

@app.route('/invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
    invoice = c.fetchone()
    conn.close()
    
    if not invoice:
        flash('Không tìm thấy hóa đơn!', 'danger')
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
        flash('Không tìm thấy hóa đơn!', 'danger')
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
        
        flash('Cập nhật hóa đơn thành công!', 'success')
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
    
    flash('Xóa hóa đơn thành công!', 'success')
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
    
    # Doanh thu
    c.execute('''
        SELECT * FROM finances 
        WHERE type = 'revenue' AND date LIKE ? 
        ORDER BY date DESC
    ''', (f'{month}%',))
    revenues = c.fetchall()
    
    # Chi phí
    c.execute('''
        SELECT * FROM finances 
        WHERE type = 'expense' AND date LIKE ? 
        ORDER BY date DESC
    ''', (f'{month}%',))
    expenses = c.fetchall()
    
    # Tổng
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
        INSERT INTO finances (type, date, amount, category, description, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data.get('type'),
        data.get('date'),
        float(data.get('amount', 0)),
        data.get('category', ''),
        data.get('description', ''),
        session['username']
    ))
    conn.commit()
    conn.close()
    
    flash('Thêm giao dịch thành công!', 'success')
    return redirect(url_for('finance'))

@app.route('/finance/delete/<int:finance_id>', methods=['POST'])
@login_required
def finance_delete(finance_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM finances WHERE id = ?', (finance_id,))
    conn.commit()
    conn.close()
    
    flash('Xóa giao dịch thành công!', 'success')
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
    
    # Hóa đơn trong khoảng
    c.execute('''
        SELECT * FROM invoices 
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    ''', (date_from, date_to))
    invoices_list = c.fetchall()
    
    # Tài chính trong khoảng
    c.execute('''
        SELECT * FROM finances 
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC
    ''', (date_from, date_to))
    finances = c.fetchall()
    
    # Tổng hợp
    total_inv = sum(i['total'] for i in invoices_list)
    total_rev = sum(f['amount'] for f in finances if f['type'] == 'revenue')
    total_exp = sum(f['amount'] for f in finances if f['type'] == 'expense')
    
    conn.close()
    
    return render_template('report.html',
                         invoices=invoices_list, finances=finances,
                         date_from=date_from, date_to=date_to,
                         total_inv=total_inv, total_rev=total_rev,
                         total_exp=total_exp, profit=total_rev - total_exp)

@app.route('/report/export')
@login_required
def report_export():
    date_from = request.args.get('date_from', '')
    date_to = date_from
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        flash('Không thể xuất Excel. Vui lòng cài đặt openpyxl.', 'danger')
        return redirect(url_for('report'))
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Bao cao"
    
    # Header
    ws['A1'] = 'BÁO CÁO TỪ NGÀY ' + date_from + ' ĐẾN ' + date_to
    ws['A1'].font = Font(bold=True, size=14)
    ws.merge_cells('A1:F1')
    
    # Invoice data
    ws['A3'] = 'HOA DON'
    ws['A3'].font = Font(bold=True, size=12)
    
    headers = ['So HD', 'Ngay', 'Cua hang', 'Tong', 'Ghi chu', 'Nguoi tao']
    for i, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=i, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='0078D4', end_color='0078D4', fill_type='solid')
        cell.font = Font(bold=True, color='FFFFFF')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT invoice_number, date, store_name, total, notes, created_by 
        FROM invoices WHERE date >= ? AND date <= ?
    ''', (date_from, date_to))
    
    row = 5
    for inv in c.fetchall():
        ws.cell(row=row, column=1, value=inv[0])
        ws.cell(row=row, column=2, value=inv[1])
        ws.cell(row=row, column=3, value=inv[2])
        ws.cell(row=row, column=4, value=inv[3])
        ws.cell(row=row, column=5, value=inv[4])
        ws.cell(row=row, column=6, value=inv[5])
        row += 1
    
    conn.close()
    
    # Save
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f'report_{date_from}_{date_to}.xlsx'
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
        flash('Vui lòng điền đầy đủ thông tin!', 'danger')
        return redirect(url_for('users'))
    
    conn = get_db()
    c = conn.cursor()
    
    # Kiểm tra trùng username
    c.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
    if c.fetchone()[0] > 0:
        flash('Tên đăng nhập đã tồn tại!', 'danger')
        conn.close()
        return redirect(url_for('users'))
    
    c.execute('''
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
    ''', (username, generate_password_hash(password), role))
    conn.commit()
    conn.close()
    
    flash(f'Tạo tài khoản "{username}" thành công!', 'success')
    return redirect(url_for('users'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def users_delete(user_id):
    if user_id == session['user_id']:
        flash('Bạn không thể xóa tài khoản của chính mình!', 'danger')
        return redirect(url_for('users'))
    
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    flash('Xóa tài khoản thành công!', 'success')
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
# Khoi tao database khi app load (chay ca khi dung gunicorn)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
