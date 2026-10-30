"""Test the Keenetic NDMS2 device tracker."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from ndms2_client import Device
from ndms2_client.client import RouterInfo
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.keenetic_ndms2.const import (
    DEFAULT_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_DATA, MOCK_NAME

CLIENT_MAC = "aa:bb:cc:dd:ee:ff"
ENTITY_ID = "device_tracker.phone"

MOCK_ROUTER_INFO = RouterInfo(
    name=MOCK_NAME,
    fw_version="3.0.4",
    fw_channel="stable",
    model="mock",
    hw_version="0000",
    manufacturer="pytest",
    vendor="foxel",
    region="RU",
)


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the Keenetic client."""
    with (
        patch("homeassistant.components.keenetic_ndms2.router.TelnetConnection"),
        patch(
            "homeassistant.components.keenetic_ndms2.router.Client", autospec=True
        ) as mock_client_class,
    ):
        client = mock_client_class.return_value
        client.get_router_info.return_value = MOCK_ROUTER_INFO
        client.get_devices.return_value = [
            Device(
                mac=CLIENT_MAC,
                name="Phone",
                ip="192.168.1.2",
                interface=DEFAULT_INTERFACE,
            )
        ]
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_name_change_renames_device(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the client name names the device and a name change renames it."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.original_name is None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "Phone"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)}
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FRIENDLY_NAME] == "Phone"

    mock_client.get_devices.return_value = [
        Device(
            mac=CLIENT_MAC,
            name="New name",
            ip="192.168.1.2",
            interface=DEFAULT_INTERFACE,
        )
    ]
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "New name"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "New name"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_without_name(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a client without a name is named by its MAC until it reports one."""
    mock_client.get_devices.return_value = [
        Device(mac=CLIENT_MAC, name="", ip="192.168.1.2", interface=DEFAULT_INTERFACE)
    ]
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "device_tracker.aa_bb_cc_dd_ee_ff"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == CLIENT_MAC
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)}

    mock_client.get_devices.return_value = [
        Device(
            mac=CLIENT_MAC, name="Phone", ip="192.168.1.2", interface=DEFAULT_INTERFACE
        )
    ]
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes[ATTR_FRIENDLY_NAME] == "Phone"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "Phone"


@pytest.mark.parametrize(
    ("device_name", "original_name", "expected_name"),
    [
        pytest.param("Restored name", None, "Restored name", id="named_device"),
        # The device of a tracker from before the client name moved to the
        # device was named by the MAC address
        pytest.param(CLIENT_MAC, "Old name", "Old name", id="old_entry"),
    ],
)
@pytest.mark.usefixtures("mock_client")
async def test_restoring_client_name_with_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_name: str,
    original_name: str | None,
    expected_name: str,
) -> None:
    """Test the name of a client not reported by the router on startup."""
    mac = "11:22:33:44:55:66"
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        name=device_name,
    )
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        f"{mac}_{mock_config_entry.entry_id}",
        suggested_object_id="restored",
        config_entry=mock_config_entry,
        device_id=device.id,
        original_name=original_name,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.restored")
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == expected_name
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == expected_name


@pytest.mark.parametrize(
    ("original_name", "expected_name"),
    [
        pytest.param("Old name", "Old name", id="original_name"),
        pytest.param(None, "11:22:33:44:55:66", id="no_name"),
    ],
)
@pytest.mark.usefixtures("mock_client")
async def test_restoring_client_name_without_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    original_name: str | None,
    expected_name: str,
) -> None:
    """Test a restored client without a device names it by its original name."""
    mac = "11:22:33:44:55:66"
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        f"{mac}_{mock_config_entry.entry_id}",
        suggested_object_id="restored",
        config_entry=mock_config_entry,
        original_name=original_name,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.restored")
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == expected_name
    entity_entry = entity_registry.async_get("device_tracker.restored")
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == expected_name
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, mac)}
