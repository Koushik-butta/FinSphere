"""
Auth service — update send_otp_email calls to use dedicated login/reset senders.
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
    try:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            return False, "Email is already registered."

        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode(), salt).decode()

        if role == 'admin':
            exists = conn.execute("SELECT id FROM families WHERE family_code=?", (family_code,)).fetchone()
            if exists:
                return False, "This Family Code already exists. Please choose a unique one."

            cursor = conn.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                (name, email, hashed_password, role)
            )
            user_id = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO families (family_code, admin_id) VALUES (?,?)",
                (family_code, user_id)
            )
            family_id = cursor.lastrowid

            conn.execute("UPDATE users SET family_id=? WHERE id=?", (family_id, user_id))
            conn.commit()

            # Seed default categories for new family
            from database import _seed_default_categories
            _seed_default_categories(conn)

            return True, "Registration successful. You can log in now."

        elif role == 'member':
            family = conn.execute("SELECT id FROM families WHERE family_code=?", (family_code,)).fetchone()
            if not family:
                return False, f"Invalid Family Code '{family_code}'. Ask your Admin for the correct one."

            family_id = family['id']
            conn.execute(
                "INSERT INTO users (name, email, password, role, family_id) VALUES (?,?,?,?,?)",
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
        conn.close()


def login_user(email, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()

    if not user:
        return None

    if not bcrypt.checkpw(password.encode(), user['password'].encode()):
        return None

    otp, expiry = generate_otp()

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET otp=?, otp_expiry=? WHERE id=?",
        (otp, expiry, user['id'])
    )
    conn.commit()
    conn.close()

    # Try to send email; if it fails, log OTP for admin visibility but continue
    email_ok = send_login_otp(user['email'], otp)
    if not email_ok:
        print(f"[OTP FALLBACK] Login OTP for {user['email']}: {otp}  (email send failed)")

    return user


def verify_user_otp(user_id, entered_otp):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return None

    if user['otp'] != entered_otp:
        conn.close()
        return None

    if user['otp_expiry']:
        try:
            otp_expiry = datetime.strptime(user['otp_expiry'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            otp_expiry = None

        if otp_expiry and otp_expiry < datetime.now():
            conn.close()
            return None

    conn.execute("UPDATE users SET otp=NULL, otp_expiry=NULL WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    return user


def forgot_password(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()

    if not user:
        return False

    otp, expiry = generate_otp()

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET reset_otp=?, reset_otp_expiry=? WHERE email=?",
        (otp, expiry, email)
    )
    conn.commit()
    conn.close()

    ok = send_reset_otp(email, otp)
    if not ok:
        print(f"[OTP FALLBACK] Reset OTP for {email}: {otp}  (email send failed)")
    return True  # Always return True so UX isn't broken


def reset_password(email, entered_otp, new_password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if not user:
        conn.close()
        return False

    if user['reset_otp'] != entered_otp:
        conn.close()
        return False

    if user['reset_otp_expiry']:
        try:
            expiry = datetime.strptime(user['reset_otp_expiry'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            expiry = None

        if expiry and expiry < datetime.now():
            conn.close()
            return False

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(new_password.encode(), salt).decode()

    conn.execute(
        "UPDATE users SET password=?, reset_otp=NULL, reset_otp_expiry=NULL WHERE email=?",
        (hashed, email)
    )
    conn.commit()
    conn.close()
    return True