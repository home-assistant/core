"""Common test values and helpers for Google Docs."""

import json

from googleapiclient.errors import HttpError
from httplib2 import Response

DOCUMENT_ID = "test-document"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def http_error(status: int) -> HttpError:
    """Build a Google client HTTP error without a live HTTP request."""
    return HttpError(
        Response({"status": str(status)}),
        json.dumps({"error": {"code": status, "message": "Test error"}}).encode(),
    )
