from celery_app import celery_app
from utils.email import (
    send_helper_verified_email,
    send_help_request_accepted_email,
    send_sos_alert_email,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, ignore_result=True)
def send_helper_verified_email_task(self, to_email, helper_name):
    """
    Celery background task for sending helper verification email.
    Uses ignore_result=True to conserve Upstash Redis free-tier commands.
    """
    try:
        success = send_helper_verified_email(to_email, helper_name)
        if not success:
            print(f"⚠️ Email dispatch unconfigured or failed for {to_email}")
        return success
    except Exception as exc:
        print(f"Retrying email task for {to_email} due to: {exc}")
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, ignore_result=True)
def send_help_request_accepted_email_task(self, to_email, user_name, helper_name, need):
    """
    Celery background task for notifying a user that their help request was accepted.
    """
    try:
        success = send_help_request_accepted_email(to_email, user_name, helper_name, need)
        if not success:
            print(f"⚠️ Help request email unconfigured or failed for {to_email}")
        return success
    except Exception as exc:
        print(f"Retrying help request email task for {to_email} due to: {exc}")
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10, ignore_result=True)
def send_sos_alert_email_task(self, admin_email, user_email, message):
    """
    Celery background task for notifying admin of an emergency SOS alert.
    """
    try:
        success = send_sos_alert_email(admin_email, user_email, message)
        if not success:
            print(f"⚠️ SOS alert email unconfigured or failed for {admin_email}")
        return success
    except Exception as exc:
        print(f"Retrying SOS email task for {admin_email} due to: {exc}")
        raise self.retry(exc=exc, countdown=10)
