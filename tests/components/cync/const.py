"""Test constants used in Cync tests."""

import time

import pycync

MOCKED_USER = pycync.User(
    "test_token",
    "test_refresh_token",
    "test_authorize_string",
    123456789,
    expires_at=(time.time() * 1000) + 3600000,
)
MOCKED_EMAIL = "test@testuser.com"
