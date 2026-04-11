"""
Auth service — handles registration, login, OTP verification, and password reset.
Uses psycopg2 (%s placeholders) connected to PostgreSQL.
"""

import bcrypt
from datetime import datetime
from database import get_db_connection
from services.otp_service import generate_otp
from utils.email_utils import send_login_otp, send_reset_otp


def register_user(name, email, password, role, family_code=None):
    if not family_code:
        return False, "Family Code is required."

    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            return False, "Email is already registered."

        salt            = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode(), salt).decode()

        if role == 'admin':
            cur.execute("SELECT id FROM families WHERE family_code=%s", (family_code,))
            if cur.fetchone():
                return False, "This Family Code already exists. Please choose a unique one."

            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s) RETURNING id",
                (name, email, hashed_password, role)
            )
            user_id = cur.fetchone()['id']

            cur.execute(
                "INSERT INTO families (family_code, admin_id) VALUES (%s,%s) RETURNING id",
                (family_code, user_id)
            )
            family_id = cur.fetchone()['id']

            cur.execute("UPDATE users SET family_id=%s WHERE id=%s", (family_id, user_id))
            conn.commit()

            # Seed default categories for the new family
            from database import _seed_default_categories
            _seed_default_categories(cur, conn)

            return True, "Registration successful. You can log in now."

        elif role == 'member':
            cur.execute("SELECT id FROM families WHERE family_code=%s", (family_code,))
            family = cur.fetchone()
            if not family:
                return False, f"Invalid Family Code '{family_code}'. Ask your Admin for the correct one."

            family_id = family['id']
            cur.execute(
                "INSERT INTO users (name, email, password, role, family_id) VALUES (%s,%s,%s,%s,%s)",
                (name, email, hashed_password, role, family_id)
            )
            conn.commit()
            return True, "Registration successful! You can log in now."

        else:
            return False, "Invalid role specified."

    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        cur.close()
        conn.close()


def login_user(email, password):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return None

    if not bcrypt.checkpw(password.encode(), user['password'].encode()):
        return None

    otp, expiry = generate_otp()

    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE users SET otp=%s, otp_expiry=%s WHERE id=%s",
        (otp, expiry, user['id'])
    )
    conn.commit()
    cur.close()
    conn.close()

    if not send_login_otp(user['email'], otp):
        # We still return the user and the generated OTP so the route can decide what to do
        # (e.g. if Render blocks SMTP, we can fallback to printing it or flashing it)
        return user, otp, False

    return user, None, True


def verify_user_otp(user_id, entered_otp):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    if not user:
        cur.close(); conn.close()
        return None

    if user['otp'] != entered_otp:
        cur.close(); conn.close()
        return None

    if user['otp_expiry']:
        try:
            otp_expiry = datetime.strptime(user['otp_expiry'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            otp_expiry = None

        if otp_expiry and otp_expiry < datetime.now():
            cur.close(); conn.close()
            return None

    cur.execute("UPDATE users SET otp=NULL, otp_expiry=NULL WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return user


def forgot_password(email):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return False

    otp, expiry = generate_otp()

    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE users SET reset_otp=%s, reset_otp_expiry=%s WHERE email=%s",
        (otp, expiry, email)
    )
    conn.commit()
    cur.close()
    conn.close()

    # Returns (success, email_sent, otp)
    email_sent = send_reset_otp(email, otp)
    return True, email_sent, otp

def reset_password(email, entered_otp, new_password):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()

    if not user:
        cur.close(); conn.close()
        return False

    if user['reset_otp'] != entered_otp:
        cur.close(); conn.close()
        return False

    if user['reset_otp_expiry']:
        try:
            expiry = datetime.strptime(user['reset_otp_expiry'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            expiry = None

        if expiry and expiry < datetime.now():
            cur.close(); conn.close()
            return False

    salt   = bcrypt.gensalt()
    hashed = bcrypt.hashpw(new_password.encode(), salt).decode()

    cur.execute(
        "UPDATE users SET password=%s, reset_otp=NULL, reset_otp_expiry=NULL WHERE email=%s",
        (hashed, email)
    )
    conn.commit()
    cur.close()
    conn.close()
    return True