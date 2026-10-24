"""Test the devolo Home Network integration setup."""

from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DeviceNotFound, DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    SHORT_UPDATE_INTERVAL,
)
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component

from . import configure_integration
from .const import CONNECTED_STATIONS, IP, IP_ALT, NO_CONNECTED_STATIONS
from .mock import MockDevice

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

STATION = CONNECTED_STATIONS[0]


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


async def test_remove_own_device(
    hass: HomeAssistant,
    mock_device: MockDevice,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the device of the config entry itself cannot be removed."""
    assert await async_setup_component(hass, "config", {})
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_device.serial_number), entry.entry_id
    )
    assert device is not None

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(device.id) is not None


async def test_remove_client(
    hass: HomeAssistant,
    mock_device: MockDevice,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing a Wi-Fi client that is not connected anymore."""
    assert await async_setup_component(hass, "config", {})
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    # A tracker only gets a device if the MAC is already known to Home Assistant
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STATION.mac_address)},
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    device = device_registry.async_get(tracker.device_id)
    assert device is not None

    client = await hass_ws_client(hass)

    # A connected client is not stale
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"

    # Emulate the client disconnecting
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await client.remove_device(device.id)
    assert response["success"]
    assert device_registry.async_get(device.id) is None
    assert entity_registry.async_get(entity_id) is None


async def test_remove_client_connected_to_other_access_point(
    hass: HomeAssistant,
    mock_device: MockDevice,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a client roaming to another devolo access point is not stale."""
    assert await async_setup_component(hass, "config", {})
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    # A tracker only gets a device if the MAC is already known to Home Assistant
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STATION.mac_address)},
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    device = device_registry.async_get(tracker.device_id)
    assert device is not None

    # Emulate the client roaming away from the first access point
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    # A second access point picks the client up
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=CONNECTED_STATIONS
    )
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: IP_ALT, CONF_PASSWORD: "test"},
        unique_id="1234567891",
    )
    second_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(device.id) is not None


async def test_remove_client_with_unreachable_access_point(
    hass: HomeAssistant,
    mock_device: MockDevice,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an access point that cannot be set up blocks removal."""
    assert await async_setup_component(hass, "config", {})
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    # A tracker only gets a device if the MAC is already known to Home Assistant
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STATION.mac_address)},
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    device = device_registry.async_get(tracker.device_id)
    assert device is not None

    # Emulate the client disconnecting from the only reachable access point
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: IP_ALT, CONF_PASSWORD: "test"},
        unique_id="1234567891",
    )
    second_entry.add_to_hass(hass)
    with patch.object(mock_device, "async_connect", side_effect=DeviceNotFound(IP_ALT)):
        await hass.config_entries.async_setup(second_entry.entry_id)
        await hass.async_block_till_done()
    assert second_entry.state is ConfigEntryState.SETUP_RETRY

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(device.id) is not None


async def test_remove_client_with_disabled_access_point(
    hass: HomeAssistant,
    mock_device: MockDevice,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a disabled access point blocks removal, as it still serves clients."""
    assert await async_setup_component(hass, "config", {})
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    # A tracker only gets a device if the MAC is already known to Home Assistant
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STATION.mac_address)},
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    device = device_registry.async_get(tracker.device_id)
    assert device is not None

    # Emulate the client disconnecting from the access point Home Assistant polls
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # A second access point is configured, but disabled in Home Assistant
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: IP_ALT, CONF_PASSWORD: "test"},
        unique_id="1234567891",
        disabled_by=ConfigEntryDisabler.USER,
    )
    second_entry.add_to_hass(hass)
    await hass.async_block_till_done()
    assert second_entry.state is ConfigEntryState.NOT_LOADED

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(device.id) is not None


async def test_remove_client_with_failing_coordinator(
    hass: HomeAssistant,
    mock_device: MockDevice,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an access point with outdated client data blocks removal."""
    assert await async_setup_component(hass, "config", {})
    entity_id = (
        f"{DEVICE_TRACKER_DOMAIN}.{STATION.mac_address.lower().replace(':', '_')}"
    )
    entry = configure_integration(hass)
    # A tracker only gets a device if the MAC is already known to Home Assistant
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STATION.mac_address)},
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    tracker = entity_registry.async_get(entity_id)
    assert tracker is not None
    device = device_registry.async_get(tracker.device_id)
    assert device is not None

    # Emulate the client disconnecting
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Emulate the access point becoming unavailable, which keeps the last data
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        side_effect=DeviceUnavailable
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(device.id) is not None


@pytest.mark.usefixtures("mock_device")
async def test_remove_device_on_unloaded_entry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that no device can be removed while the config entry is not loaded."""
    assert await async_setup_component(hass, "config", {})
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, STATION.mac_address)},
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert device_registry.async_get(device.id) is not None


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
