"""Tests for the Adax integration."""

from typing import Any

from homeassistant.components.adax.const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CLOUD_CONFIG = {
    ACCOUNT_ID: 12345,
    CONF_PASSWORD: "pswd",
    CONNECTION_TYPE: CLOUD,
}

LOCAL_CONFIG = {
    CONF_IP_ADDRESS: "192.168.1.12",
    CONF_TOKEN: "TOKEN-123",
    CONF_UNIQUE_ID: "11:22:33:44:55:66",
    CONNECTION_TYPE: LOCAL,
}


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Adax integration in Home Assistant."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
