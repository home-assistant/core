"""Tests for the Trafikverket Camera integration."""
from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_LOCATION

ENTRY_CONFIG = {
    CONF_API_KEY: "1234567890",
    CONF_ID: "1234",
}

ENTRY_CONFIG_OLD_CONFIG = {
    CONF_API_KEY: "1234567890",
    CONF_LOCATION: "Test location",
}
