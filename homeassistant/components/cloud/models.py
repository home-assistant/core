"""Models for the cloud integration."""

import dataclasses
from typing import Any

from hass_nabucasa import AutoLoginController, LoginFailedReason

from .const import DOMAIN

# Spelled out rather than derived from the reason, so the keys stay greppable and
# a reason hass_nabucasa adds later does not silently point at a missing string.
AUTO_LOGIN_FAILED_TRANSLATION_KEYS = {
    LoginFailedReason.CLOUD_ERROR: "auto_login_failed_cloud_error",
    LoginFailedReason.TIMEOUT: "auto_login_failed_timeout",
    LoginFailedReason.UNEXPECTED_ERROR: "auto_login_failed_unexpected_error",
}


def auto_login_failure(reason: LoginFailedReason) -> dict[str, Any]:
    """Describe why an auto-login gave up, for the frontend to render."""
    return {
        "reason": reason,
        "translation_domain": DOMAIN,
        "translation_key": AUTO_LOGIN_FAILED_TRANSLATION_KEYS.get(
            reason, "auto_login_failed_unexpected_error"
        ),
    }


@dataclasses.dataclass
class PendingAutoLogin:
    """A registration waiting for its email confirmation to log in."""

    email: str
    controller: AutoLoginController | None
    failed_reason: LoginFailedReason | None = None

    def mark_failed(self, reason: LoginFailedReason) -> None:
        """Record that the retry loop gave up before logging in."""
        self.controller = None
        self.failed_reason = reason

    def as_status(self) -> dict[str, Any]:
        """Describe the registration for the cloud status."""
        return {
            "email": self.email,
            "failed": (
                None
                if self.failed_reason is None
                else auto_login_failure(self.failed_reason)
            ),
        }
