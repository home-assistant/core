"""Tests for the nmap_tracker device tracker."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.nmap_tracker.const import DOMAIN, TRACKER_SCAN_INTERVAL
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import CLIENT_MAC, scan_result

ENTITY_ID = "device_tracker.phone"
RESTORED_ENTITY_ID = "device_tracker.restored"


async def _async_setup_at_startup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the entry before Home Assistant has started."""
    hass.set_state(CoreState.not_running)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


NO_HOSTNAME = [
    pytest.param("", id="empty_hostname"),
    # The scanner then reports the IP address as hostname
    pytest.param(None, id="no_hostnames"),
]


@pytest.mark.parametrize("no_hostname", NO_HOSTNAME)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hostname_change_renames_device(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    no_hostname: str | None,
) -> None:
    """Test the hostname names the device, and a hostname change renames it."""
    await _async_setup_at_startup(hass, mock_config_entry)

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.original_name is None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "phone"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)}
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FRIENDLY_NAME] == "phone"

    mock_port_scanner.scan.return_value = scan_result("laptop.lan")
    freezer.tick(timedelta(seconds=TRACKER_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "laptop"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "laptop"

    # A missing hostname does not replace the name of the device
    mock_port_scanner.scan.return_value = scan_result(no_hostname)
    freezer.tick(timedelta(seconds=TRACKER_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_FRIENDLY_NAME] == "laptop"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "laptop"


@pytest.mark.parametrize("no_hostname", NO_HOSTNAME)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_without_hostname(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    no_hostname: str | None,
) -> None:
    """Test a client without a hostname names its device by vendor."""
    mock_port_scanner.scan.return_value = scan_result(no_hostname)
    await _async_setup_at_startup(hass, mock_config_entry)

    entity_id = "device_tracker.vendor_dd_ee_ff"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "Vendor DD:EE:FF"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)}
    assert (
        hass.states.get(entity_id).attributes[ATTR_FRIENDLY_NAME] == "Vendor DD:EE:FF"
    )


@pytest.mark.parametrize("no_hostname", NO_HOSTNAME)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_startup_without_hostname_keeps_device_name(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    no_hostname: str | None,
) -> None:
    """Test a scan without a hostname at startup keeps the name of the device."""
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, CLIENT_MAC)},
        name="laptop",
    )
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        CLIENT_MAC,
        suggested_object_id="laptop",
        config_entry=mock_config_entry,
        device_id=device.id,
    )
    mock_port_scanner.scan.return_value = scan_result(no_hostname)

    await _async_setup_at_startup(hass, mock_config_entry)

    state = hass.states.get("device_tracker.laptop")
    assert state.state == STATE_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "laptop"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "laptop"


@pytest.mark.parametrize(
    ("device_name", "original_name", "expected_name"),
    [
        pytest.param("Restored name", None, "Restored name", id="named_device"),
        # The device of a tracker from before the device name moved to the
        # device was named by the hostname or the MAC address
        pytest.param("11:22:33:44:55:66", "Old name", "Old name", id="old_entry"),
    ],
)
async def test_restoring_client_name_with_device(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_name: str,
    original_name: str | None,
    expected_name: str,
) -> None:
    """Test the name of a client not found in the initial scan."""
    mac = "11:22:33:44:55:66"
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        name=device_name,
    )
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        mac,
        suggested_object_id="restored",
        config_entry=mock_config_entry,
        device_id=device.id,
        original_name=original_name,
    )

    await _async_setup_at_startup(hass, mock_config_entry)

    state = hass.states.get(RESTORED_ENTITY_ID)
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == expected_name
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == expected_name


async def test_restoring_client_name_without_device(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a restored client without a device names it by its original name."""
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        "11:22:33:44:55:66",
        suggested_object_id="restored",
        config_entry=mock_config_entry,
        original_name="Old name",
    )

    await _async_setup_at_startup(hass, mock_config_entry)

    state = hass.states.get(RESTORED_ENTITY_ID)
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Old name"
    entity_entry = entity_registry.async_get(RESTORED_ENTITY_ID)
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "Old name"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66")}
