from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from services.auth_service import register_user, login_user, verify_user_otp, forgot_password, reset_password

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('doc.dashboard'))
    return render_template('home.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        family_code = request.form.get('family_code', '').strip().upper()
        
        success, message = register_user(
            request.form['name'],
            request.form['email'],
            request.form['password'],
            role,
            family_code
        )
        
        if not success:
            flash(message, 'danger')
            return render_template('register.html')
            
        flash(message, 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        result = login_user(request.form['email'], request.form['password'])

        if result:
            session['temp_user'] = result['id']
            flash('OTP sent to your email. Please enter it below.', 'success')
            return redirect(url_for('auth.verify_otp'))

        flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

@auth_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        temp_user = session.get('temp_user')
        if not temp_user:
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))

        user = verify_user_otp(temp_user, request.form['otp'])

        if user:
            session.pop('temp_user', None)
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            session['family_id'] = user['family_id']
            return redirect(url_for('doc.dashboard'))

        flash('Invalid or expired OTP. Please try again.', 'danger')

    return render_template('otp_verify.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password_route():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')

        success = forgot_password(email)
        if success:
            session['reset_email'] = email
            flash('A password reset OTP has been sent to your email.', 'success')
            return redirect(url_for('auth.reset_password_route'))
        else:
            flash('If that email is registered, an OTP has been sent.', 'info')
            return render_template('forgot_password.html')

    return render_template('forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_route():
    reset_email = session.get('reset_email')
    if not reset_email:
        flash('Session expired. Please start the password reset again.', 'warning')
        return redirect(url_for('auth.forgot_password_route'))

    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')

        if len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('reset_password.html')

        success = reset_password(reset_email, otp, new_password)
        if success:
            session.pop('reset_email', None)
            flash('Password reset successfully! Please log in with your new password.', 'success')
            return redirect(url_for('auth.login'))

        flash('Invalid or expired OTP. Please try again.', 'danger')

    return render_template('reset_password.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.index'))