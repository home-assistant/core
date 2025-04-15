"""Define const for Volvo unit tests."""

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

MOCK_ACCESS_TOKEN = "mock-access-token"

REDIRECT_URI = "https://example.com/auth/external/callback"

SERVER_TOKEN_RESPONSE = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "token_type": "Bearer",
    "expires_in": 60,
}
