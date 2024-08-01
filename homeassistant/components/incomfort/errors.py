"""Exceptions raised by Intergas InComfort integration."""

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError


class NotFound(HomeAssistantError):
    """Raise exception if no Lan2RF Gateway was found."""

    translation_domain = HOMEASSISTANT_DOMAIN
    translation_key = "not_found"


class NoHeaters(ConfigEntryNotReady):
    """Raise exception if no heaters are found."""

    translation_domain = HOMEASSISTANT_DOMAIN
    translation_key = "no_heaters"


class InConfortTimeout(ConfigEntryNotReady):
    """Raise exception if no heaters are found."""

    translation_domain = HOMEASSISTANT_DOMAIN
    translation_key = "timeout_error"


class InConfortUnknownError(ConfigEntryNotReady):
    """Raise exception if no heaters are found."""

    translation_domain = HOMEASSISTANT_DOMAIN
    translation_key = "unknown"
