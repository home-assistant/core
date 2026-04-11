"""IZone tests."""

from unittest.mock import AsyncMock

import pizone

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Mock integration setup."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def setup_controller(
    hass: HomeAssistant, mock_discovery: AsyncMock, mock_controller: AsyncMock
) -> None:
    """Mock integration setup."""
    get_discovery_service(mock_discovery).controller_discovered(mock_controller)
    await hass.async_block_till_done()


def get_discovery_service(mock_discovery: AsyncMock) -> pizone.Listener:
    """Get the DiscoveryService instance from the mock discovery."""
    return mock_discovery.mock_calls[0][1][0]
