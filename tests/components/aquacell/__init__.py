"""Tests for the Aquacell integration."""

from aioaquacell import Brand

from homeassistant.components.aquacell.const import (
    CONF_BRAND,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_CONFIG_ENTRY = {
    CONF_EMAIL: "test@test.com",
    CONF_PASSWORD: "test-password",
    CONF_REFRESH_TOKEN: "refresh-token",
    CONF_REFRESH_TOKEN_CREATION_TIME: 0,
    CONF_BRAND: Brand.AQUACELL,
}

TEST_CONFIG_ENTRY_WITHOUT_BRAND = {
    CONF_EMAIL: "test@test.com",
    CONF_PASSWORD: "test-password",
    CONF_REFRESH_TOKEN: "refresh-token",
    CONF_REFRESH_TOKEN_CREATION_TIME: 0,
}

TEST_USER_INPUT = {
    CONF_EMAIL: "test@test.com",
    CONF_PASSWORD: "test-password",
    CONF_BRAND: "aquacell",
}

DSN = "DSN"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
