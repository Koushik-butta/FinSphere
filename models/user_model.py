"""
User model helpers — thin wrappers around common user queries.
Uses psycopg2 (%s placeholders).
"""

from database import get_db_connection


def get_user_by_id(user_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def get_user_by_email(email):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def get_users_by_family(family_id):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, name, email, role FROM users WHERE family_id=%s",
        (family_id,)
    )
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users
