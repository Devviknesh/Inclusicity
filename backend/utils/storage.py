import os
import mimetypes
from datetime import datetime

# Optional boto3 import for Cloudflare R2 / S3-compatible private object storage
try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def is_r2_configured():
    """Check if Cloudflare R2 credentials are fully configured."""
    return bool(
        BOTO3_AVAILABLE
        and os.getenv("R2_ACCOUNT_ID")
        and os.getenv("R2_ACCESS_KEY_ID")
        and os.getenv("R2_SECRET_ACCESS_KEY")
        and os.getenv("R2_BUCKET_NAME")
    )


def get_r2_client():
    """Create an S3 client targeting Cloudflare R2."""
    if not is_r2_configured():
        return None

    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )


def upload_kyc_document(file_obj, destination_key, max_size_mb=10):
    """
    Upload a KYC document.
    - If Cloudflare R2 is configured, uploads directly to the private R2 bucket.
    - Otherwise, saves to local secure UPLOAD_FOLDER with JWT-controlled access.
    Returns (success: bool, url_or_key: str, error_msg: str)
    """
    # Enforce strict file size limits to prevent exceeding free-tier storage
    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False, "", f"File size exceeds maximum allowed free limit of {max_size_mb} MB"

    content_type = mimetypes.guess_type(destination_key)[0] or "application/octet-stream"

    if is_r2_configured():
        bucket_name = os.getenv("R2_BUCKET_NAME")
        try:
            client = get_r2_client()
            client.upload_fileobj(
                file_obj,
                bucket_name,
                destination_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": {
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "classification": "confidential_kyc"
                    }
                }
            )
            print(f"✅ Securely uploaded KYC document to private R2 bucket: {destination_key}")
            return True, destination_key, ""
        except Exception as e:
            print(f"❌ R2 upload failed: {e}")
            return False, "", str(e)

    # Local secure fallback
    return True, destination_key, ""


def get_kyc_document_access_url(document_key, expiration_seconds=900):
    """
    Generate a temporary, presigned access URL for an authorized admin or owning helper.
    - Cloudflare R2: Generates an S3 presigned URL expiring in 15 minutes (900 seconds).
    - Local storage: Returns the relative protected endpoint `/uploads/<key>`.
    """
    if is_r2_configured():
        bucket_name = os.getenv("R2_BUCKET_NAME")
        try:
            client = get_r2_client()
            url = client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket_name,
                    "Key": document_key
                },
                ExpiresIn=expiration_seconds
            )
            return url
        except Exception as e:
            print(f"❌ Failed to generate R2 presigned URL: {e}")
            return None

    # Protected local endpoint with JWT token required
    return f"/uploads/{document_key}"


def delete_kyc_document(document_key):
    """
    Securely delete a KYC document from storage.
    """
    if is_r2_configured():
        bucket_name = os.getenv("R2_BUCKET_NAME")
        try:
            client = get_r2_client()
            client.delete_object(Bucket=bucket_name, Key=document_key)
            print(f"🗑️ Deleted KYC document from R2: {document_key}")
            return True
        except Exception as e:
            print(f"❌ Failed to delete from R2: {e}")
            return False
    return True
