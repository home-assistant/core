"""Tests for the Google Generative AI Conversation integration."""

from google.genai.errors import APIError, ClientError

API_ERROR_500 = APIError(
    500,
    {"message": "Internal Server Error", "status": "internal-error"},
)
CLIENT_ERROR_BAD_REQUEST = ClientError(
    400,
    {"message": "Bad Request", "status": "invalid-argument"},
)
CLIENT_ERROR_API_KEY_INVALID = ClientError(
    400,
    {"message": "'reason': API_KEY_INVALID", "status": "unauthorized"},
)
