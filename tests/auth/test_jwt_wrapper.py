"""Tests for the Home Assistant auth jwt_wrapper module."""

import jwt
import pytest

from homeassistant.auth import jwt_wrapper


async def test_all_default_options_are_in_verify_options() -> None:
    """Test that all default options in _VERIFY_OPTIONS."""
    for option in jwt_wrapper._PyJWTWithVerify._get_default_options():
        assert option in jwt_wrapper._VERIFY_OPTIONS


async def test_reject_access_token_with_impossible_large_size() -> None:
    """Test rejecting access tokens with impossible sizes."""
    with pytest.raises(jwt.DecodeError):
        jwt_wrapper.unverified_hs256_token_decode("a" * 10000)
