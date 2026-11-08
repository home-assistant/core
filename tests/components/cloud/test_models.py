"""Tests for the cloud integration models."""

from typing import cast

from hass_nabucasa import LoginFailedReason
import pytest

from homeassistant.components.cloud.models import auto_login_failure_key


@pytest.mark.parametrize(
    ("reason", "translation_key"),
    [
        (None, None),
        (LoginFailedReason.TIMEOUT, "auto_login_failed_timeout"),
        (LoginFailedReason.CLOUD_ERROR, "auto_login_failed_cloud_error"),
        (
            LoginFailedReason.UNEXPECTED_ERROR,
            "auto_login_failed_unexpected_error",
        ),
        (
            cast(LoginFailedReason, "brand_new_reason"),
            "auto_login_failed_unexpected_error",
        ),
    ],
)
def test_auto_login_failure_key(
    reason: LoginFailedReason | None, translation_key: str | None
) -> None:
    """Test every reason maps to a string that exists."""
    assert auto_login_failure_key(reason) == translation_key
