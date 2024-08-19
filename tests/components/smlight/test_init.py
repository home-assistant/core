"Test SMLIGHT SLZB device integration initialization."

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry."""
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test async_setup_entry when authentication fails."""
    mock_smlight_client.check_auth_needed.return_value = True
    mock_smlight_client.authenticate.side_effect = SmlightAuthError
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update failed due to connection error."""

    await setup_integration(hass, mock_config_entry)
    entity = hass.states.get("sensor.mock_title_core_chip_temp")
    assert entity.state is not STATE_UNAVAILABLE

    mock_smlight_client.get_info.side_effect = SmlightConnectionError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.mock_title_core_chip_temp")
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry information."""
    entry = await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot
