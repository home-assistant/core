"""Tests for the Google Generative AI Conversation integration."""

from unittest.mock import Mock

from google.genai.errors import APIError, ClientError
import httpx

API_ERROR_500 = APIError(
    500,
    Mock(
        __class__=httpx.Response,
        json=Mock(
            return_value={
                "message": "Internal Server Error",
                "status": "internal-error",
            }
        ),
    ),
)
CLIENT_ERROR_BAD_REQUEST = ClientError(
    400,
    Mock(
        __class__=httpx.Response,
        json=Mock(
            return_value={
                "message": "Bad Request",
                "status": "invalid-argument",
            }
        ),
    ),
)
CLIENT_ERROR_API_KEY_INVALID = ClientError(
    400,
    Mock(
        __class__=httpx.Response,
        json=Mock(
            return_value={
                "message": "'reason': API_KEY_INVALID",
                "status": "unauthorized",
            }
        ),
    ),
)
