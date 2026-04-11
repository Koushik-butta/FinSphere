from database import get_db_connection
try:
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT current_database();")
        db_name = cur.fetchone()['current_database']
        print(f"SUCCESS! Connected to Neon DB: {db_name}")
        cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';")
        tables = [r['tablename'] for r in cur.fetchall()]
        print(f"Tables present: {', '.join(tables)}")
    conn.close()
except Exception as e:
    import traceback
    traceback.print_exc()
