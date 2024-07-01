"""Test the Dio Chacon Cover init."""

import logging
from unittest.mock import AsyncMock

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .conftest import MOCK_COVER_DEVICE

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_cover_unload_entry(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the creation and values of the Dio Chacon covers."""

    mock_config_entry.add_to_hass(hass)

    mock_dio_chacon_client.search_all_devices.return_value = MOCK_COVER_DEVICE
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Tests coverage for unload actions.
    mock_dio_chacon_client.disconnect.return_value = {}
    await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_cover_shutdown_event(
    hass: HomeAssistant,
    mock_dio_chacon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the creation and values of the Dio Chacon covers."""

    mock_config_entry.add_to_hass(hass)

    mock_dio_chacon_client.search_all_devices.return_value = MOCK_COVER_DEVICE
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Tests coverage for stop action.
    mock_dio_chacon_client.disconnect.return_value = {}
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
