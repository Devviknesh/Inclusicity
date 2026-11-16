from celery_app import celery_app
from utils.email import send_helper_verified_email


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def send_helper_verified_email_task(self, to_email, helper_name):
    return send_helper_verified_email(
        to_email=to_email,
        helper_name=helper_name,
    )
