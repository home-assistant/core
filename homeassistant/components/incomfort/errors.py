"""Exceptions raised by `InComfort` integration."""

from homeassistant.core import DOMAIN
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)


class NotFound(HomeAssistantError):
    """Raise exception if no Lan2RF Gateway was found."""

    translation_domain = DOMAIN
    translation_key = "not_found"


class NoHeaters(ConfigEntryNotReady):
    """Raise exception if no heaters are found."""

    translation_domain = DOMAIN
    translation_key = "no_heaters"


class InConfortTimeout(ConfigEntryNotReady):
    """Raise exception if no heaters are found."""

    translation_domain = DOMAIN
    translation_key = "timeout_error"


class InConfortUnknownError(ConfigEntryNotReady):
    """Raise exception if no heaters are found."""

    translation_domain = DOMAIN
    translation_key = "unknown_error"


def raise_from_error_code(errors: dict[str, str]) -> None:
    """Raise an error by error code."""
    code = next(iter(errors.items()))[1]
    if code == "auth_error":
        raise ConfigEntryAuthFailed("Incorrect credentials")
    if code == "not_found":
        raise NotFound
    if code == "no_heaters":
        raise NoHeaters
    if code == "timeout_error":
        raise InConfortTimeout
    raise InConfortUnknownError
