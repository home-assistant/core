"""Tests for the CoolBot Pro integration."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> bool:
    """Set up the CoolBot Pro integration for testing."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return result


async def push(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Deliver a push the way the client does, by calling its listeners."""
    for listener in list(mock_client.listeners):
        listener()
    await hass.async_block_till_done()
