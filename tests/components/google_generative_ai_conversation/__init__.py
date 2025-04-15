"""Tests for the Google Generative AI Conversation integration."""

from unittest.mock import Mock

from google.genai.errors import ClientError
import httpx

CLIENT_ERROR_500 = ClientError(
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
