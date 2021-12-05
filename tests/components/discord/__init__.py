"""Tests for the Discord integration."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.const import CONF_NAME, CONF_TOKEN

TOKEN = "abc123"
NAME = "Discord Bot"

CONF_DATA = {
    CONF_TOKEN: TOKEN,
    CONF_NAME: NAME,
}

CONF_CONFIG_FLOW = {
    CONF_TOKEN: TOKEN,
    CONF_NAME: NAME,
}


async def create_mocked_discord():
    """Create mocked discord."""
    mocked_discord = AsyncMock()
    mocked_discord.id = "1234567890"
    return mocked_discord


def patch_discord_info(mocked_discord):
    """Patch discord info."""
    return patch(
        "discord.Client.application_info",
        return_value=mocked_discord,
    )


def mock_response():
    """Mock response."""
    response = Mock()
    response.status = 404
    return response
