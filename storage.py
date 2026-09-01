"""Small Google Cloud Storage helper for booking documents."""
import os
import re
from datetime import datetime, timezone


BUCKET_NAME = os.getenv("GOOGLE_CLOUD_BUCKET", "portea-doc-storage")


def safe_filename(filename: str) -> str:
    """Keep only filename characters that are safe for a cloud object path."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", filename or "document")


def upload_booking_document(booking_ref: str, filename: str, content: bytes, content_type: str | None) -> str:
    """Upload one private clinical document and return its gs:// location."""
    from google.cloud import storage

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object_name = f"booking-documents/{booking_ref}/{timestamp}-{safe_filename(filename)}"

    client = storage.Client()
    blob = client.bucket(BUCKET_NAME).blob(object_name)
    blob.upload_from_string(content, content_type=content_type or "application/octet-stream")

    return f"gs://{BUCKET_NAME}/{object_name}"
