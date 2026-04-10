"""
User model helpers — thin wrappers around common user queries.
"""

from database import get_db_connection


def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user


def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return user


def get_users_by_family(family_id):
    conn = get_db_connection()
    users = conn.execute(
        "SELECT id, name, email, role FROM users WHERE family_id=?",
        (family_id,)
    ).fetchall()
    conn.close()
    return users
