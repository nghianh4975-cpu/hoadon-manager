import sqlite3, os, sys
sys.stdout.reconfigure(encoding='utf-8')

db_files = [f for f in os.listdir('.') if f.endswith('.db')]
print('DB files:', db_files)

for f in db_files:
    conn = sqlite3.connect(f)
    conn.text_factory = str
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print('Tables in', f, ':', [t[0] for t in tables])
    if ('materials',) in tables:
        c.execute('PRAGMA table_info(materials)')
        print('  materials schema:', c.fetchall())
        c.execute('SELECT id, name, group_id FROM materials ORDER BY id DESC LIMIT 10')
        rows = c.fetchall()
        for r in rows:
            print('  mat:', r)
    if ('imports',) in tables:
        c.execute('SELECT id, date, material_id, total_price FROM imports ORDER BY id DESC LIMIT 5')
        print('  recent imports:', c.fetchall())
        c.execute("SELECT id, name, group_id FROM materials WHERE group_id IS NULL OR group_id = '' ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        for r in rows:
            print('  no_group mat:', r)
    conn.close()
