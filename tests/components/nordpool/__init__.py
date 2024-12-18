"""Tests for the Nord Pool integration."""

from homeassistant.components.nordpool.const import CONF_AREAS
from homeassistant.const import CONF_CURRENCY

ENTRY_CONFIG = {
    CONF_AREAS: ["SE3", "SE4"],
    CONF_CURRENCY: "SEK",
}
