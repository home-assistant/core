"""Test the devolo Home Network integration setup."""

from unittest.mock import MagicMock, patch

from devolo_plc_api.exceptions.device import DeviceNotFound
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.devolo_home_network import (
    async_remove_config_entry_device,
)
from homeassistant.components.devolo_home_network.const import (
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
)
from homeassistant.components.devolo_home_network.coordinator import (
    DevoloHomeNetworkData,
    DevoloWifiConnectedStationsGetCoordinator,
)
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms

from . import configure_integration
from .const import CONNECTED_STATIONS, IP
from .mock import MockDevice

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_device")
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = configure_integration(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_device_not_found(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_network.Device.async_connect",
        side_effect=DeviceNotFound(IP),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_device")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload entry."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_hass_stop(hass: HomeAssistant, mock_device: MockDevice) -> None:
    """Test homeassistant stop event."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_device.async_disconnect.assert_called_once()


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_device: MockDevice,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing an absent tracked client and rediscovering it later."""
    entry = configure_integration(hass)
    tracked_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, CONNECTED_STATIONS[0].mac_address)},
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}."
        f"{CONNECTED_STATIONS[0].mac_address.lower().replace(':', '_')}"
    )
    tracker_entry = entity_registry.async_get(entity_id)
    assert tracker_entry is not None
    assert tracker_entry.device_id == tracked_device.id

    configured_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_device.serial_number), entry.entry_id
    )
    assert configured_device is not None
    assert not await async_remove_config_entry_device(hass, entry, configured_device)
    assert not await async_remove_config_entry_device(hass, entry, tracked_device)

    coordinator = entry.runtime_data.coordinators[CONNECTED_WIFI_CLIENTS]
    assert isinstance(coordinator, DevoloWifiConnectedStationsGetCoordinator)
    coordinator.async_set_updated_data({})
    assert CONNECTED_STATIONS[0].mac_address in coordinator.tracked_wifi_clients
    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )

    other_coordinator = MagicMock()
    other_coordinator.data = {CONNECTED_STATIONS[0].mac_address: CONNECTED_STATIONS[0]}
    other_coordinator.last_update_success = True
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="other-entry",
        state=ConfigEntryState.LOADED,
        unique_id="other-device",
    )
    other_entry.runtime_data = DevoloHomeNetworkData(
        device=mock_device,
        coordinators={CONNECTED_WIFI_CLIENTS: other_coordinator},
    )
    other_entry.add_to_hass(hass)

    assert not await async_remove_config_entry_device(hass, entry, tracked_device)
    other_coordinator.data = {}
    other_coordinator.last_update_success = False
    assert not await async_remove_config_entry_device(hass, entry, tracked_device)
    other_coordinator.last_update_success = True
    assert await async_remove_config_entry_device(hass, entry, tracked_device)
    assert CONNECTED_STATIONS[0].mac_address not in coordinator.tracked_wifi_clients

    device_registry.async_remove_device(tracked_device.id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None

    coordinator.async_set_updated_data(
        {CONNECTED_STATIONS[0].mac_address: CONNECTED_STATIONS[0]}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is not None


async def test_remove_config_entry_device_rejects_unrelated_device(
    hass: HomeAssistant,
    mock_device: MockDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device without a tracked Wi-Fi MAC is rejected."""
    entry = configure_integration(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unrelated_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_integration", "unrelated")},
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:5E:00:53:02")},
    )
    assert not await async_remove_config_entry_device(hass, entry, unrelated_device)

    child_device = device_registry.async_get_or_create_child(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "child")},
        parent_device_id=unrelated_device.id,
    )
    assert not await async_remove_config_entry_device(hass, entry, child_device)


async def test_remove_config_entry_device_without_wifi(
    hass: HomeAssistant,
    mock_nonwifi_device: MockDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a tracked device from a non-Wi-Fi entry is rejected."""
    entry = configure_integration(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    tracked_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, CONNECTED_STATIONS[0].mac_address)},
    )
    assert not await async_remove_config_entry_device(hass, entry, tracked_device)


@pytest.mark.parametrize(
    "device", ["mock_device", "mock_repeater_device", "mock_ipv6_device"]
)
async def test_device(
    hass: HomeAssistant,
    device: str,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    request: pytest.FixtureRequest,
) -> None:
    """Test device setup."""
    mock_device: MockDevice = request.getfixturevalue(device)
    entry = configure_integration(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    device_info = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_device.serial_number), entry.entry_id
    )
    assert device_info == snapshot


@pytest.mark.parametrize(
    ("device", "expected_platforms"),
    [
        (
            "mock_device",
            (
                BINARY_SENSOR_DOMAIN,
                BUTTON_DOMAIN,
                DEVICE_TRACKER_DOMAIN,
                IMAGE_DOMAIN,
                SENSOR_DOMAIN,
                SWITCH_DOMAIN,
                UPDATE_DOMAIN,
            ),
        ),
        (
            "mock_repeater_device",
            (
                BUTTON_DOMAIN,
                DEVICE_TRACKER_DOMAIN,
                IMAGE_DOMAIN,
                SENSOR_DOMAIN,
                SWITCH_DOMAIN,
                UPDATE_DOMAIN,
            ),
        ),
        (
            "mock_nonwifi_device",
            (
                BINARY_SENSOR_DOMAIN,
                BUTTON_DOMAIN,
                SENSOR_DOMAIN,
                SWITCH_DOMAIN,
                UPDATE_DOMAIN,
            ),
        ),
    ],
)
async def test_platforms(
    hass: HomeAssistant,
    device: str,
    expected_platforms: set[str],
    request: pytest.FixtureRequest,
) -> None:
    """Test platform assembly."""
    request.getfixturevalue(device)
    entry = configure_integration(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    platforms = [platform.domain for platform in async_get_platforms(hass, DOMAIN)]
    assert len(platforms) == len(expected_platforms)
    assert all(platform in platforms for platform in expected_platforms)
