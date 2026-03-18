"""Constants for the SunSynk integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.exceptions import HomeAssistantError
else:
    try:
        from homeassistant.exceptions import HomeAssistantError
    except ImportError:
        HomeAssistantError = Exception

DOMAIN = "sunsynk"


class SunSynkError(HomeAssistantError):
    """Base exception for SunSynk integration."""

    translation_domain = DOMAIN
    translation_key = "sunsynk_error"


class SunSynkAuthError(SunSynkError):
    """Error during authentication."""

    translation_key = "auth_error"


class SunSynkApiError(SunSynkError):
    """Error communicating with the SunSynk API."""

    translation_key = "api_error"


CONF_REGION = "region"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_PLANT_IGNORE_LIST = "plant_ignore_list"
CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 60

REGIONS = {
    0: "Region 1 (Production - pv.inteless.com)",
    1: "Region 2 (Alternative - api.sunsynk.net)",
}

# Valid 30-minute time slot values for sell times
VALID_TIME_SLOTS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
