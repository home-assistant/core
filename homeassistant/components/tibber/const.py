"""Constants for Tibber integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN

if TYPE_CHECKING:
    from . import TibberRuntimeData

type TibberConfigEntry = ConfigEntry[TibberRuntimeData]


CONF_LEGACY_ACCESS_TOKEN = CONF_ACCESS_TOKEN

AUTH_IMPLEMENTATION = "auth_implementation"
DATA_HASS_CONFIG = "tibber_hass_config"
DOMAIN = "tibber"
MANUFACTURER = "Tibber"
DATA_API_DEFAULT_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "data-api-user-read",
    "data-api-chargers-read",
    "data-api-energy-systems-read",
    "data-api-homes-read",
    "data-api-thermostats-read",
    "data-api-vehicles-read",
    "data-api-inverters-read",
]
