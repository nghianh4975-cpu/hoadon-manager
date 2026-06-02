"""
Migrate data from local SQLite database to Render PostgreSQL.
Run this ONCE after deploying to Render and setting DATABASE_URL.
Usage: python migrate_to_pg.py
"""
import sqlite3
import psycopg2
import os

LOCAL_DB = 'hoadon.db'
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Please set it and try again.")
    exit(1)

# Ket noi SQLite
sqlite_conn = sqlite3.connect(LOCAL_DB)
sqlite_conn.row_factory = sqlite3.Row
sc = sqlite_conn.cursor()

# Ket noi PostgreSQL
pg_conn = psycopg2.connect(DATABASE_URL)
pc = pg_conn.cursor()

# Tao bang
pc.execute('''
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

pc.execute('''
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

pc.execute('''
CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    unit VARCHAR(20),
    group_id INTEGER REFERENCES material_groups(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

pc.execute('''
CREATE TABLE IF NOT EXISTS material_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7) DEFAULT '#6c757d',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

pc.execute('''
CREATE TABLE IF NOT EXISTS imports (
    id SERIAL PRIMARY KEY,
    date VARCHAR(10) NOT NULL,
    material_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id),
    notes TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

pc.execute('''
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE,
    date VARCHAR(10),
    store_name VARCHAR(200),
    items TEXT,
    subtotal REAL,
    discount_percent REAL,
    tax_percent REAL,
    total REAL,
    notes TEXT,
    image_data TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

pg_conn.commit()
print("Tables created.")

def migrate_table(pg_table, sqlite_table, columns):
    sc.execute(f'SELECT * FROM {sqlite_table}')
    rows = sc.fetchall()
    if not rows:
        print(f"  {sqlite_table}: no data, skip.")
        return
    placeholders = ','.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO {pg_table} ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    for row in rows:
        pc.execute(insert_sql, [row[col] for col in columns])
    pg_conn.commit()
    print(f"  {sqlite_table}: migrated {len(rows)} rows.")

# Disable FK cho import vi co the tham chieu supplier chua ton tai
pc.execute('SET session_replication_role = replica')

print("Migrating users...")
migrate_table('users', 'users', ['id', 'username', 'password_hash', 'role'])

print("Migrating suppliers...")
migrate_table('suppliers', 'suppliers', ['id', 'name', 'phone', 'address', 'notes'])

print("Migrating material_groups...")
migrate_table('material_groups', 'material_groups', ['id', 'name', 'color', 'sort_order'])

print("Migrating materials...")
migrate_table('materials', 'materials', ['id', 'name', 'unit', 'group_id'])

print("Migrating imports...")
migrate_table('imports', 'imports', ['id', 'date', 'material_id', 'quantity', 'unit_price', 'total_price', 'supplier_id', 'notes', 'created_by'])

print("Migrating invoices...")
migrate_table('invoices', 'invoices', ['id', 'invoice_number', 'date', 'store_name', 'items', 'subtotal', 'discount_percent', 'tax_percent', 'total', 'notes', 'image_data', 'created_by'])

pc.execute('SET session_replication_role = DEFAULT')

sqlite_conn.close()
pg_conn.close()
print("\nMigration complete!")
