"""
HTML OTP email utility — professional branded templates.
Sender name appears as: Family Finance System <email>
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SENDER_EMAIL


# ── HTML Template Builder ────────────────────────────────────────────────────

def _build_html(otp: str, purpose: str, extra_note: str = '') -> str:
    """Return a fully-styled HTML email body."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Family Finance System — OTP</title>
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;
             background:#f0f4f8;color:#1e293b;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:16px;
                      box-shadow:0 4px 24px rgba(0,0,0,0.09);overflow:hidden;
                      max-width:560px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0d47a1 0%,#1565c0 60%,#1976d2 100%);
                       padding:32px 40px;text-align:center;">
              <table cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td align="center">
                    <span style="display:inline-flex;align-items:center;gap:10px;">
                      <span style="font-size:28px;">🔐</span>
                      <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:800;
                                 letter-spacing:-0.3px;">Family Finance System</h1>
                    </span>
                    <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">
                      Secure Document Management
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px 28px;">
              <p style="margin:0 0 6px;font-size:15px;color:#64748b;">Hello,</p>
              <p style="margin:0 0 28px;font-size:16px;line-height:1.6;color:#1e293b;">
                Your One-Time Password (OTP) for
                <strong style="color:#1a56db;">{purpose}</strong> is:
              </p>

              <!-- OTP Box -->
              <div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);
                          border:2px solid #93c5fd;border-radius:14px;
                          text-align:center;padding:24px 20px;margin-bottom:28px;">
                <p style="margin:0 0 8px;font-size:12px;font-weight:700;
                           letter-spacing:2px;text-transform:uppercase;color:#1d4ed8;">
                  Your OTP Code
                </p>
                <span style="font-size:42px;font-weight:900;letter-spacing:12px;
                             color:#1e3a8a;font-family:'Courier New',monospace;
                             display:block;margin:4px 0;">
                  {otp}
                </span>
                <p style="margin:8px 0 0;font-size:13px;color:#2563eb;font-weight:600;">
                  ⏱ Valid for 5 minutes only
                </p>
              </div>

              {extra_note}

              <!-- Security Notice -->
              <div style="background:#fef9c3;border-left:4px solid #f59e0b;
                          border-radius:0 8px 8px 0;padding:14px 16px;margin-bottom:24px;">
                <p style="margin:0;font-size:13px;color:#92400e;line-height:1.6;">
                  <strong>🚨 Security Notice:</strong> Do not share this OTP with anyone.
                  Family Finance System will never ask for your OTP via call or chat.
                </p>
              </div>

              <p style="margin:0;font-size:14px;color:#64748b;line-height:1.6;">
                If you did not request this OTP, please ignore this email and ensure
                your account is secure.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;border-top:1px solid #e2e8f0;
                       padding:20px 40px;text-align:center;">
              <p style="margin:0;font-size:13px;color:#94a3b8;">
                — <strong style="color:#1e293b;">Family Finance System</strong> &nbsp;|&nbsp;
                Secure &middot; Private &middot; Trusted
              </p>
              <p style="margin:6px 0 0;font-size:11px;color:#cbd5e1;">
                This is an automated message. Please do not reply.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


def _build_plain(otp: str, purpose: str) -> str:
    return (
        f"Hello,\n\n"
        f"Your OTP for {purpose} is:\n\n"
        f"  OTP: {otp}\n\n"
        f"This OTP is valid for 5 minutes.\n\n"
        f"Security Notice: Do not share this OTP with anyone.\n\n"
        f"— Family Finance System"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def send_otp_email(recipient: str, otp: str,
                   subject: str = "Login Verification – Family Finance System",
                   purpose: str = "Login Verification",
                   extra_note: str = '') -> bool:
    """
    Send an HTML-formatted OTP email using Resend HTTP API.
    Sender display name: Family Finance System <sender_email>
    """
    try:
        import urllib.request
        import json
        from config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME
        
        if not BREVO_API_KEY:
            print("[EMAIL] Error: BREVO_API_KEY is not set.")
            return False

        url = "https://api.brevo.com/v3/smtp/email"
        
        payload = {
            "sender": {
                "name": SENDER_NAME,
                "email": SENDER_EMAIL
            },
            "to": [
                {
                    "email": recipient
                }
            ],
            "subject": subject,
            "htmlContent": _build_html(otp, purpose, extra_note),
            "textContent": _build_plain(otp, purpose)
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'accept': 'application/json',
            'api-key': BREVO_API_KEY,
            'content-type': 'application/json'
        })
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in [200, 201]:
                return True
            print(f"[EMAIL] Brevo API returned status {response.status}")
            return False

    except Exception as e:
        print(f"[EMAIL] Failed to send OTP via Brevo HTTP API: {e}")
        return False


def send_login_otp(recipient: str, otp: str) -> bool:
    return send_otp_email(
        recipient=recipient,
        otp=otp,
        subject="Login Verification – Family Finance System",
        purpose="Login Verification",
    )


def send_reset_otp(recipient: str, otp: str) -> bool:
    extra = """
    <div style="background:#fce7f3;border-left:4px solid #ec4899;
                border-radius:0 8px 8px 0;padding:14px 16px;margin-bottom:24px;">
      <p style="margin:0;font-size:13px;color:#9d174d;line-height:1.6;">
        <strong>🔑 Password Reset:</strong> If you did not request a password reset,
        your account may be at risk. Change your password immediately.
      </p>
    </div>
    """
    return send_otp_email(
        recipient=recipient,
        otp=otp,
        subject="Password Reset – Family Finance System",
        purpose="Password Reset Verification",
        extra_note=extra,
    )