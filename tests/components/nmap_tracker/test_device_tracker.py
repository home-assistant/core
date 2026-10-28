"""Tests for the nmap_tracker device tracker."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.nmap_tracker.const import (
    CONF_HOME_INTERVAL,
    CONF_HOSTS_EXCLUDE,
    CONF_HOSTS_LIST,
    CONF_MAC_EXCLUDE,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
    TRACKER_SCAN_INTERVAL,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

CLIENT_MAC = "aa:bb:cc:dd:ee:ff"
CLIENT_IP = "192.168.1.2"
ENTITY_ID = "device_tracker.phone"
RESTORED_ENTITY_ID = "device_tracker.restored"


def _scan_result(hostname: str) -> dict[str, Any]:
    """Return an nmap scan result with the client up."""
    return {
        "scan": {
            CLIENT_IP: {
                "status": {"state": "up", "reason": "arp-response"},
                "addresses": {"mac": CLIENT_MAC.upper()},
                "hostnames": [{"name": hostname, "type": "PTR"}],
                "vendor": {CLIENT_MAC.upper(): "Vendor"},
            }
        }
    }


@pytest.fixture
def mock_port_scanner() -> Generator[MagicMock]:
    """Mock the nmap port scanner."""
    with (
        patch("homeassistant.components.nmap_tracker.PortScanner") as mock_scanner,
        patch(
            "homeassistant.components.nmap_tracker.aiooui.is_loaded",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nmap_tracker.aiooui.get_vendor",
            return_value="Vendor",
        ),
    ):
        scanner = mock_scanner.return_value
        scanner.scan.return_value = _scan_result("phone.lan")
        yield scanner


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_HOSTS_LIST: ["192.168.1.0/24"],
            CONF_HOSTS_EXCLUDE: [],
            CONF_MAC_EXCLUDE: [],
            CONF_HOME_INTERVAL: 0,
            CONF_OPTIONS: DEFAULT_OPTIONS,
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry


async def _async_setup_at_startup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the entry before Home Assistant has started."""
    hass.set_state(CoreState.not_running)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hostname_change_renames_device(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the hostname names the device, and a hostname change renames it."""
    await _async_setup_at_startup(hass, mock_config_entry)

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.original_name is None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "phone"
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FRIENDLY_NAME] == "phone"

    mock_port_scanner.scan.return_value = _scan_result("laptop.lan")
    freezer.tick(timedelta(seconds=TRACKER_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_HOME
    assert state.attributes[ATTR_FRIENDLY_NAME] == "laptop"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "laptop"

    # A missing hostname names the client by vendor, which does not replace the
    # name of its device
    mock_port_scanner.scan.return_value = _scan_result("")
    freezer.tick(timedelta(seconds=TRACKER_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_FRIENDLY_NAME] == "laptop"
    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.name == "laptop"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_without_hostname(
    hass: HomeAssistant,
    mock_port_scanner: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a client without a hostname names its device by vendor."""
    mock_port_scanner.scan.return_value = _scan_result("")
    await _async_setup_at_startup(hass, mock_config_entry)

    entity_id = "device_tracker.vendor_dd_ee_ff"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name == "Vendor DD:EE:FF"
    assert (
        hass.states.get(entity_id).attributes[ATTR_FRIENDLY_NAME] == "Vendor DD:EE:FF"
    )


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
