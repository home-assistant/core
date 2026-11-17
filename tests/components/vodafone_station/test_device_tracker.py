"""Define tests for the Vodafone Station device tracker."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vodafone_station.const import SCAN_INTERVAL
from homeassistant.components.vodafone_station.coordinator import CONSIDER_HOME_SECONDS
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import setup_integration
from .const import DEVICE_1_HOST, DEVICE_1_MAC


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.vodafone_station.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("client_name", "expected_device_name"),
    [
        pytest.param(DEVICE_1_HOST, DEVICE_1_HOST, id="hostname"),
        pytest.param("", DEVICE_1_MAC, id="no_hostname"),
    ],
)
async def test_device_info(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    client_name: str,
    expected_device_name: str,
) -> None:
    """Test the tracked client device is named by hostname, else by MAC address."""
    mock_vodafone_station_router.get_devices_data.return_value[
        DEVICE_1_MAC
    ].name = client_name
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, DEVICE_1_MAC), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == expected_device_name
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, DEVICE_1_MAC)}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_consider_home(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if device is considered not_home when disconnected."""
    await setup_integration(hass, mock_config_entry)

    device_tracker = f"device_tracker.{DEVICE_1_HOST}"

    assert (state := hass.states.get(device_tracker))
    assert state.state == STATE_HOME

    mock_vodafone_station_router.get_devices_data.return_value[
        DEVICE_1_MAC
    ].connected = False

    freezer.tick(SCAN_INTERVAL + CONSIDER_HOME_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(device_tracker))
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_already_tracked_devices(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that already tracked devices are skipped when signal fires again."""
    await setup_integration(hass, mock_config_entry)

    # Capture the number of existing device_tracker entities before firing the signal
    tracker_count_before = len(hass.states.async_all(Platform.DEVICE_TRACKER))
    assert tracker_count_before > 0

    coordinator = mock_config_entry.runtime_data

    # Fire signal_device_new again; all devices are already tracked so no new
    # entities should be added and the continue branch in async_add_new_tracked_entities
    # is exercised.
    async_dispatcher_send(hass, coordinator.signal_device_new)
    await hass.async_block_till_done()

    # Ensure no additional device_tracker entities were created
    tracker_count_after = len(hass.states.async_all(Platform.DEVICE_TRACKER))
    assert tracker_count_after == tracker_count_before
