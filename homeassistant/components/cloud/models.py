"""Models for the cloud integration."""

from hass_nabucasa import LoginFailedReason

# Spelled out rather than derived from the reason, so the keys stay greppable and
# a reason hass_nabucasa adds later does not silently point at a missing string.
AUTO_LOGIN_FAILED_TRANSLATION_KEYS = {
    LoginFailedReason.CLOUD_ERROR: "auto_login_failed_cloud_error",
    LoginFailedReason.TIMEOUT: "auto_login_failed_timeout",
    LoginFailedReason.UNEXPECTED_ERROR: "auto_login_failed_unexpected_error",
}


def auto_login_failure_key(reason: LoginFailedReason | None) -> str | None:
    """Return the string to render for an auto-login that gave up."""
    if reason is None:
        return None
    return AUTO_LOGIN_FAILED_TRANSLATION_KEYS.get(
        reason, "auto_login_failed_unexpected_error"
    )
