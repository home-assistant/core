"""Define const for Volvo unit tests."""

CLIENT_ID = "vid-dc-1234"
CLIENT_SECRET = "5678"
LEGACY_CLIENT_ID = "dc-1234"

DEFAULT_API_KEY = "abcdef0123456879abcdef"
DEFAULT_MODEL = "xc40_electric_2024"
DEFAULT_VIN = "YV1ABCDEFG1234567"

MOCK_ACCESS_TOKEN = "mock-access-token"

REDIRECT_URI = "https://example.com/auth/external/callback"

SERVER_TOKEN_RESPONSE = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "token_type": "Bearer",
    "expires_in": 60,
}
