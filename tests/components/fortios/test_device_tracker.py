"""Test shared FortiOS polling and tracker discovery."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiofortiosapi import FortiOSConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.fortios.client import FortiOSDevice
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MAC

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_discovery_and_grace(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Create only online clients, share polls, and preserve grace after disappearance."""
    other_mac = "11:22:33:44:55:66"
    mock_client.update.return_value[other_mac] = FortiOSDevice(
        other_mac, "laptop", False
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert hass.states.get("device_tracker.laptop") is None
    coordinator = mock_config_entry.runtime_data
    mock_client.update.return_value = {
        MAC: FortiOSDevice(MAC, "phone", True),
        other_mac: FortiOSDevice(other_mac, "laptop", True),
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(hass.states.async_all("device_tracker")) == 2
    assert mock_client.update.call_count == 2
    mock_client.update.return_value = {}
    await coordinator.async_refresh()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    freezer.tick(timedelta(seconds=181))
    await coordinator.async_refresh()
    assert hass.states.get("device_tracker.phone").state == STATE_NOT_HOME
    mock_client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert len(hass.states.async_all("device_tracker")) == 2
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_empty_initial_scan(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Discovery remains active when the first scan is empty."""
    mock_client.update.return_value = {}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.async_all("device_tracker") == []
    mock_client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME


async def test_poll_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A failed scan makes states unavailable and recovers on the next scan."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.update.side_effect = FortiOSConnectionError
    await mock_config_entry.runtime_data.async_refresh()
    assert hass.states.get("device_tracker.phone").state == STATE_UNAVAILABLE
    mock_client.update.side_effect = None
    await mock_config_entry.runtime_data.async_refresh()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME


@pytest.mark.parametrize("failure_method", ["connect", "update"])
async def test_setup_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    failure_method: str,
) -> None:
    """A failure in either setup request schedules a retry."""
    getattr(mock_client, failure_method).side_effect = FortiOSConnectionError
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
