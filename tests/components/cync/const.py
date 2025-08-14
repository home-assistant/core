"""Test constants used in Cync tests."""

import pycync

MOCKED_USER = pycync.User(
    "test_token",
    "test_refresh_token",
    "test_authorize_string",
    123456789,
    expires_at=3600,
)
MOCKED_EMAIL = "test@testuser.com"
