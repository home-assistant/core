"""Tests for the luci device tracker."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntityStateAttribute,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_1, MOCK_DEVICE_2

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_luci_client")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker entities are created."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a disconnected device stays home until consider_home has elapsed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_HOME

    # Simulate device disconnecting
    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_2]

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Still home, the default consider_home of 180 seconds has not elapsed yet
    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_HOME
    # The last known details are kept while the device is considered home
    assert state.attributes[ScannerEntityStateAttribute.IP] == MOCK_DEVICE_1.ip

    freezer.tick(timedelta(seconds=180))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("consider_home", "expected_state"),
    [
        pytest.param(0, STATE_NOT_HOME, id="disabled"),
        pytest.param(900, STATE_HOME, id="maximum"),
    ],
)
async def test_consider_home_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    consider_home: int,
    expected_state: str,
) -> None:
    """Test the consider_home option controls how long a device stays home."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_CONSIDER_HOME: consider_home}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_2]

    freezer.tick(timedelta(seconds=300))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == expected_state
