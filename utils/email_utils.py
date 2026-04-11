"""
OTP email utility — uses Brevo (Sendinblue) HTTP API.
Render blocks outbound SMTP, so we use Brevo's REST API instead.
Set BREVO_API_KEY as an environment variable in Render dashboard.
"""

import os
import json
import urllib.request
import urllib.error

# Brevo API key — set this as an environment variable on Render
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
SENDER_EMAIL  = os.environ.get('SENDER_EMAIL', 'noreply@finsphere.app')
SENDER_NAME   = 'FinSphere – Family Finance'


# ── HTML Template Builder ────────────────────────────────────────────────────

def _build_html(otp: str, purpose: str, extra_note: str = '') -> str:
    """Return a fully-styled HTML email body."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>FinSphere — OTP</title>
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
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:800;">
                🔐 FinSphere
              </h1>
              <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">
                Secure Family Document Management
              </p>
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
                  FinSphere will never ask for your OTP via call or chat.
                </p>
              </div>

              <p style="margin:0;font-size:14px;color:#64748b;line-height:1.6;">
                If you did not request this OTP, please ignore this email.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;border-top:1px solid #e2e8f0;
                       padding:20px 40px;text-align:center;">
              <p style="margin:0;font-size:13px;color:#94a3b8;">
                — <strong style="color:#1e293b;">FinSphere</strong> &nbsp;|&nbsp;
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
        f"— FinSphere"
    )


# ── Brevo HTTP API Sender ────────────────────────────────────────────────────

def _send_via_brevo(recipient: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send email via Brevo (Sendinblue) HTTP API — works on Render."""
    if not BREVO_API_KEY:
        print(f"[EMAIL] BREVO_API_KEY not set. Cannot send email to {recipient}.")
        return False

    payload = json.dumps({
        "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to":          [{"email": recipient}],
        "subject":     subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=payload,
        headers={
            'accept':       'application/json',
            'api-key':      BREVO_API_KEY,
            'content-type': 'application/json',
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.getcode()
            if status in (200, 201):
                print(f"[EMAIL] OTP sent to {recipient} via Brevo.")
                return True
            print(f"[EMAIL] Brevo returned status {status}")
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"[EMAIL] Brevo HTTP error {e.code}: {body}")
        return False
    except Exception as e:
        print(f"[EMAIL] Brevo send failed: {e}")
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def send_otp_email(recipient: str, otp: str,
                   subject: str = "Login Verification – FinSphere",
                   purpose: str = "Login Verification",
                   extra_note: str = '') -> bool:
    html = _build_html(otp, purpose, extra_note)
    text = _build_plain(otp, purpose)
    ok   = _send_via_brevo(recipient, subject, html, text)
    if not ok:
        # Always log OTP so admin can retrieve it from Render logs if email fails
        print(f"[OTP FALLBACK] {purpose} OTP for {recipient}: {otp}")
    return ok


def send_login_otp(recipient: str, otp: str) -> bool:
    return send_otp_email(
        recipient=recipient,
        otp=otp,
        subject="Login Verification – FinSphere",
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
        subject="Password Reset – FinSphere",
        purpose="Password Reset Verification",
        extra_note=extra,
    )