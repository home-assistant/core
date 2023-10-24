"""Tests for the Trafikverket Camera integration."""
from __future__ import annotations

from homeassistant.components.trafikverket_camera.const import CONF_LOCATION
from homeassistant.const import CONF_API_KEY

ENTRY_CONFIG = {
    CONF_API_KEY: "1234567890",
    CONF_LOCATION: "Test location",
}
