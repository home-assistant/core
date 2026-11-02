"""Tests for the Swisscom Internet-Box device tracker."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.swisscom.const import DOMAIN
from homeassistant.components.swisscom.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .const import TEST_FORMATTED_MAC

CLIENT_MAC = "11:22:33:44:55:66"
OTHER_MAC = "66:55:44:33:22:11"


def _client(mac: str, name: str | None) -> MagicMock:
    """Return a mocked LAN client of the Internet-Box."""
    client = MagicMock(key=mac, phys_address=mac, ip_address="192.168.1.2", active=True)
    client.name = name
    return client


@pytest.mark.parametrize(
    ("client_name", "expected_entity_id", "expected_device_name"),
    [
        pytest.param("phone", "device_tracker.phone", "phone", id="named"),
        pytest.param(
            None, "device_tracker.11_22_33_44_55_66", CLIENT_MAC, id="unnamed"
        ),
    ],
)
async def test_device_info(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client_name: str | None,
    expected_entity_id: str,
    expected_device_name: str,
) -> None:
    """Test the tracker describes the tracked device and is named after it."""
    mock_swisscom_client.get_devices.return_value = [_client(CLIENT_MAC, client_name)]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(expected_entity_id)
    assert entity_entry is not None
    assert entity_entry.original_name is None
    assert entity_entry.device_id is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)}
    assert device.name == expected_device_name


@pytest.mark.parametrize(
    ("initial_name", "entity_id"),
    [
        pytest.param("phone", "device_tracker.phone", id="renamed"),
        pytest.param("", "device_tracker.11_22_33_44_55_66", id="name_learned"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_renamed_on_hostname_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    initial_name: str,
    entity_id: str,
) -> None:
    """Test the tracked device follows a hostname change of the client."""
    client = _client(CLIENT_MAC, initial_name)
    mock_swisscom_client.get_devices.return_value = [client]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client.name = "laptop"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, CLIENT_MAC), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "laptop"
    assert hass.states.get(entity_id).attributes["friendly_name"] == "laptop"

    # A client which loses its name keeps the device name
    client.name = ""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "laptop"
    assert hass.states.get(entity_id).attributes["friendly_name"] == "laptop"


async def test_disabled_tracker_device_renamed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device of a disabled tracker follows a hostname change."""
    client = _client(CLIENT_MAC, "phone")
    mock_swisscom_client.get_devices.return_value = [client]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # Trackers are disabled by default
    assert hass.states.get("device_tracker.phone") is None

    client.name = "laptop"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, CLIENT_MAC), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "laptop"


async def test_reload_without_name_keeps_device_name(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a client without name keeps the name of its existing device."""
    mock_swisscom_client.get_devices.return_value = [_client(CLIENT_MAC, "phone")]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_swisscom_client.get_devices.return_value = [
        _client(CLIENT_MAC, ""),
        _client(OTHER_MAC, ""),
    ]
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, CLIENT_MAC), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "phone"
    # Only a new device is named after the MAC address
    new_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, OTHER_MAC), mock_config_entry.entry_id
    )
    assert new_device is not None
    assert new_device.name == OTHER_MAC


@pytest.mark.parametrize(
    ("mac", "removable"),
    [
        pytest.param(CLIENT_MAC, False, id="known_client"),
        pytest.param(OTHER_MAC, True, id="forgotten_client"),
        pytest.param(TEST_FORMATTED_MAC, False, id="internet_box"),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mac: str,
    removable: bool,
) -> None:
    """Test only devices the Internet-Box no longer knows can be removed."""
    assert await async_setup_component(hass, "config", {})
    mock_swisscom_client.get_devices.return_value = [
        _client(CLIENT_MAC, "phone"),
        _client(OTHER_MAC, "laptop"),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, TEST_FORMATTED_MAC)},
    )

    # The Internet-Box forgets the second client
    mock_swisscom_client.get_devices.return_value = [_client(CLIENT_MAC, "phone")]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), mock_config_entry.entry_id
    )
    assert device is not None
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device.id)
    assert response["success"] is removable
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), mock_config_entry.entry_id
        )
        is None
    ) is removable


@pytest.mark.parametrize(
    ("mac", "removable"),
    [
        pytest.param(CLIENT_MAC, True, id="client"),
        pytest.param(TEST_FORMATTED_MAC, False, id="internet_box"),
    ],
)
async def test_remove_config_entry_device_unloaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mac: str,
    removable: bool,
) -> None:
    """Test removing a device of an unloaded config entry."""
    assert await async_setup_component(hass, "config", {})
    mock_swisscom_client.get_devices.return_value = [_client(CLIENT_MAC, "phone")]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, TEST_FORMATTED_MAC)},
    )
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), mock_config_entry.entry_id
    )
    assert device is not None
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device.id)
    assert response["success"] is removable
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), mock_config_entry.entry_id
        )
        is None
    ) is removable


async def test_removed_client_rediscovered(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a client returning after its device was removed is tracked again."""
    assert await async_setup_component(hass, "config", {})
    client = _client(CLIENT_MAC, "phone")
    mock_swisscom_client.get_devices.return_value = [client]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_swisscom_client.get_devices.return_value = []
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, CLIENT_MAC), mock_config_entry.entry_id
    )
    assert device is not None
    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(device.id)
    assert response["success"]
    assert entity_registry.async_get("device_tracker.phone") is None

    mock_swisscom_client.get_devices.return_value = [client]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_entry = entity_registry.async_get("device_tracker.phone")
    assert entity_entry is not None
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, CLIENT_MAC), mock_config_entry.entry_id
    )
    assert device is not None
    assert entity_entry.device_id == device.id


@pytest.mark.usefixtures("mock_swisscom_client")
async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing an unexpected child device is rejected."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    parent_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "parent")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "child")},
        parent_device_id=parent_device.id,
    )

    ws_client = await hass_ws_client(hass)
    response = await ws_client.remove_device(child_device.id)
    assert not response["success"]
    assert device_registry.async_get(child_device.id) is not None
