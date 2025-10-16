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
SECOND_MOCKED_USER = pycync.User(
    "test_token_2",
    "test_refresh_token_2",
    "test_authorize_string_2",
    987654321,
    expires_at=(time.time() * 1000) + 3600000,
)
MOCKED_EMAIL = "test@testuser.com"
