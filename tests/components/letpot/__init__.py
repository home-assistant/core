"""Tests for the LetPot integration."""

from letpot.models import AuthenticationInfo

AUTHENTICATION = AuthenticationInfo(
    access_token="access_token",
    access_token_expires=0,
    refresh_token="refresh_token",
    refresh_token_expires=0,
    user_id="a1b2c3d4e5f6a1b2c3d4e5f6",
    email="email@example.com",
)
