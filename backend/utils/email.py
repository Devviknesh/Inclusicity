import os
import json
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email_via_brevo_api(api_key, sender_email, sender_name, to_email, to_name, subject, text_content, html_content=None):
    """
    Send an email via the Brevo (formerly Sendinblue) HTTPS REST API.
    Brevo offers 300 free emails per day forever without requiring a paid subscription.
    Using HTTPS API (port 443) bypasses cloud hosting SMTP port blocks (Render, Railway, etc.).
    """
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    payload = {
        "sender": {
            "name": sender_name or "InclusiCity",
            "email": sender_email or "noreply@inclusicity.com"
        },
        "to": [
            {
                "email": to_email,
                "name": to_name or to_email.split("@")[0]
            }
        ],
        "subject": subject,
        "textContent": text_content
    }

    if html_content:
        payload["htmlContent"] = html_content
    else:
        # Simple HTML fallback
        payload["htmlContent"] = f"<p style='font-family: sans-serif; white-space: pre-wrap;'>{text_content}</p>"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            if status_code in (200, 201):
                print(f"✅ [Brevo API] Email sent successfully to {to_email}: {response_body}")
                return True
            else:
                print(f"⚠️ [Brevo API] Unexpected status code {status_code}: {response_body}")
                return False
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        if e.code == 402 or "quota" in error_body.lower():
            print(f"⚠️ [Brevo API Quota] Free tier daily quota (300 emails/day) reached. Skipping to preserve zero-cost: {error_body}")
        else:
            print(f"❌ [Brevo API Error] HTTP {e.code}: {error_body}")
        return False
    except Exception as e:
        print(f"❌ [Brevo API Exception] Failed to send email to {to_email}: {e}")
        return False


def send_email_via_smtp(mail_server, mail_port, mail_username, mail_password, to_email, subject, text_content):
    """
    Send an email via standard SMTP with STARTTLS (e.g. Gmail SMTP port 587).
    """
    msg = MIMEMultipart()
    msg["From"] = mail_username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_content, "plain"))

    try:
        server = smtplib.SMTP(mail_server, int(mail_port), timeout=10)
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ [SMTP] Email successfully sent to: {to_email}")
        return True
    except Exception as e:
        print(f"❌ [SMTP Error] Email send failed to {to_email}: {e}")
        return False


def send_email(to_email, subject, text_content, html_content=None, to_name=None):
    """
    Unified email dispatcher:
    1. First checks for Brevo HTTPS API credentials (preferred for cloud hosting without SMTP ports).
    2. Falls back to standard SMTP (e.g., Gmail on port 587).
    3. If unconfigured, logs a notice and returns False gracefully without failing caller operations.
    """
    brevo_api_key = os.getenv("BREVO_API_KEY")
    brevo_sender = os.getenv("BREVO_SENDER_EMAIL") or os.getenv("MAIL_USERNAME") or "noreply@inclusicity.com"

    if brevo_api_key:
        return send_email_via_brevo_api(
            api_key=brevo_api_key,
            sender_email=brevo_sender,
            sender_name="InclusiCity Accessibility Platform",
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )

    # Fallback to SMTP
    mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_port = int(os.getenv("MAIL_PORT", 587))

    # Also check Flask current_app config if available
    try:
        from flask import current_app
        if current_app:
            mail_server = current_app.config.get("MAIL_SERVER", mail_server)
            mail_username = current_app.config.get("MAIL_USERNAME", mail_username)
            mail_password = current_app.config.get("MAIL_PASSWORD", mail_password)
            mail_port = int(current_app.config.get("MAIL_PORT", mail_port))
    except Exception:
        pass

    if mail_server and mail_username and mail_password:
        return send_email_via_smtp(
            mail_server=mail_server,
            mail_port=mail_port,
            mail_username=mail_username,
            mail_password=mail_password,
            to_email=to_email,
            subject=subject,
            text_content=text_content
        )

    print(f"⚠️ Email dispatch skipped: neither BREVO_API_KEY nor SMTP credentials configured in environment.")
    return False


def send_helper_verified_email(to_email, helper_name):
    """Notify a volunteer helper that their verification documents have been approved by admin."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    try:
        from flask import current_app
        if current_app:
            frontend_url = current_app.config.get("FRONTEND_URL", frontend_url).rstrip("/")
    except Exception:
        pass

    subject = "InclusiCity – Helper Account Verified ✅"
    body = f"""Hello {helper_name},

🎉 Congratulations!

Your helper account on InclusiCity has been verified by our team.
You can now log in and start accepting accessibility requests.

Login here:
{frontend_url}/login

Thank you for supporting an inclusive city ❤️

– InclusiCity Team
"""
    return send_email(to_email=to_email, subject=subject, text_content=body, to_name=helper_name)


def send_help_request_accepted_email(to_email, user_name, helper_name, need):
    """Notify a user that a volunteer helper has accepted their help request."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    subject = f"InclusiCity – Helper Assigned to Your Request: {need} 🤝"
    body = f"""Hello {user_name},

Good news! Volunteer {helper_name} has accepted your help request for "{need}".

You can view details and connect with your helper directly on your dashboard:
{frontend_url}/dashboard

Thank you for using InclusiCity!

– InclusiCity Team
"""
    return send_email(to_email=to_email, subject=subject, text_content=body, to_name=user_name)


def send_sos_alert_email(admin_email, user_email, message):
    """Notify administrator immediately when an emergency SOS alert is triggered."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    subject = "🚨 URGENT: InclusiCity Emergency SOS Alert Triggered"
    body = f"""URGENT ALERT:

An emergency SOS has been triggered on the InclusiCity platform.

User Email: {user_email}
Message: {message}

Please inspect the Admin Dashboard immediately:
{frontend_url}/admin

– InclusiCity Safety System
"""
    return send_email(to_email=admin_email, subject=subject, text_content=body, to_name="Administrator")
