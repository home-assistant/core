"""Tests for the Discord integration."""

from unittest.mock import AsyncMock, Mock, patch

import nextcord

from homeassistant.components.discord.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TOKEN = "abc123"
NAME = "Discord Bot"

CONF_INPUT = {CONF_API_TOKEN: TOKEN}

CONF_DATA = {
    CONF_API_TOKEN: TOKEN,
    CONF_NAME: NAME,
}


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id="1234567890",
    )
    entry.add_to_hass(hass)
    return entry


def mocked_discord_info():
    """Create mocked discord."""
    mocked_discord = AsyncMock()
    mocked_discord.id = "1234567890"
    mocked_discord.name = NAME
    return patch(
        "homeassistant.components.discord.config_flow.nextcord.Client.application_info",
        return_value=mocked_discord,
    )


def patch_discord_login():
    """Patch discord info."""
    return patch("homeassistant.components.discord.config_flow.nextcord.Client.login")


def mock_exception():
    """Mock response."""
    response = Mock()
    response.status = 404
    return nextcord.HTTPException(response, "")
