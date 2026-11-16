import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_helper_verified_email(to_email, helper_name):
    # Retrieve configuration from Flask current_app or environment variables
    mail_server = None
    mail_username = None
    mail_password = None
    mail_port = 587
    frontend_url = "http://localhost:5173"

    try:
        from flask import current_app
        if current_app:
            mail_server = current_app.config.get("MAIL_SERVER")
            mail_username = current_app.config.get("MAIL_USERNAME")
            mail_password = current_app.config.get("MAIL_PASSWORD")
            mail_port = current_app.config.get("MAIL_PORT", 587)
            frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
    except Exception:
        pass

    # Fallback to direct environment variables
    mail_server = mail_server or os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_username = mail_username or os.getenv("MAIL_USERNAME")
    mail_password = mail_password or os.getenv("MAIL_PASSWORD")
    mail_port = int(mail_port or os.getenv("MAIL_PORT", 587))
    frontend_url = (frontend_url or os.getenv("FRONTEND_URL", "http://localhost:5173")).rstrip("/")

    print(f"MAIL DISPATCH ATTEMPT: server={mail_server}, to={to_email}")

    if not mail_server or not mail_username or not mail_password:
        print("⚠️ SMTP credentials not fully configured in environment. Skipping email dispatch.")
        return False

    subject = "InclusiCity – Helper Account Verified ✅"

    body = f"""Hello {helper_name},

🎉 Congratulations!

Your helper account on InclusiCity has been verified by our team.

You can now log in and start accepting requests.

Login here:
{frontend_url}/login

Thank you for supporting an inclusive city ❤️

– InclusiCity Team
"""

    msg = MIMEMultipart()
    msg["From"] = mail_username
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()

        print(f"✅ Email successfully sent to: {to_email}")
        return True

    except Exception as e:
        print(f"❌ Email send failed to {to_email}: {e}")
        return False
