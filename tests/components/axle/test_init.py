"""Test integration setup and unloading."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioaxlevpp import AxleAuthenticationError, AxleConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unload the entry and its entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("sensor.axle_energy_import_export").state == "unavailable"
    mock_client.get_event.reset_mock()
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.get_event.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AxleAuthenticationError(), ConfigEntryState.SETUP_ERROR),
        (AxleConnectionError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    error: Exception,
    expected: ConfigEntryState,
) -> None:
    """Handle authentication and retryable connection failures."""
    mock_client.get_event.side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected
