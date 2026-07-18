"""Tests for the Cisco IOS device tracker."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pexpect import pxssh

from homeassistant import config_entries
from homeassistant.components.cisco_ios.const import DOMAIN
from homeassistant.components.cisco_ios.coordinator import (
    UPDATE_INTERVAL,
    CiscoIOSArpScanner,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONFIG, MOCK_DEVICE_DATA, MOCK_HOST

from tests.common import MockConfigEntry, async_fire_time_changed

ARP_OUTPUT = """show ip arp
Protocol  Address          Age (min)  Hardware Addr   Type   Interface
Internet  192.168.1.1             -   0027.d32d.0123  ARPA   GigabitEthernet0
Internet  192.168.1.100           0   001d.ec02.07ab  ARPA   GigabitEthernet0
Internet  192.168.1.101          12   0027.d32d.4567  ARPA   GigabitEthernet0
malformed line"""


async def test_device_tracker_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scanner: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    # Pre-register one entity, as ScannerEntity disables new entities by
    # default when no matching device exists in the device registry.
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        "00:1D:EC:02:07:AB",
        suggested_object_id="tracked_phone",
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == DOMAIN
    ]
    assert len(entries) == 2
    assert {entry.unique_id for entry in entries} == set(MOCK_DEVICE_DATA)

    assert (state := hass.states.get("device_tracker.tracked_phone"))
    assert state.state == STATE_HOME


async def test_new_device_creates_entity_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scanner: MagicMock,
    entity_registry: EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device discovered after setup creates a new entity."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            "device_tracker", DOMAIN, "AA:BB:CC:DD:EE:FF"
        )
        is None
    )

    mock_scanner.return_value.get_devices.return_value = {
        **MOCK_DEVICE_DATA,
        "AA:BB:CC:DD:EE:FF": "192.168.1.102",
    }
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, "AA:BB:CC:DD:EE:FF"
    )


async def test_device_disconnect_sets_not_home(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scanner: MagicMock,
    entity_registry: EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device disappearing from the ARP table is marked not home."""
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        "00:1D:EC:02:07:AB",
        suggested_object_id="tracked_phone",
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("device_tracker.tracked_phone"))
    assert state.state == STATE_HOME

    mock_scanner.return_value.get_devices.return_value = {}
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("device_tracker.tracked_phone"))
    assert state.state == STATE_NOT_HOME


async def test_device_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scanner: MagicMock,
    entity_registry: EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the entities become unavailable when the router is unreachable."""
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        "00:1D:EC:02:07:AB",
        suggested_object_id="tracked_phone",
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_scanner.return_value.get_devices.side_effect = pxssh.ExceptionPxssh("fail")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("device_tracker.tracked_phone"))
    assert state.state == STATE_UNAVAILABLE


async def test_setup_scanner_legacy_platform_imports_config_entry(
    hass: HomeAssistant, mock_scanner: MagicMock
) -> None:
    """Test legacy device tracker setup triggers config flow import."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == MOCK_CONFIG
    assert entries[0].source == config_entries.SOURCE_IMPORT


async def test_setup_scanner_legacy_platform_creates_issue_on_cannot_connect(
    hass: HomeAssistant, mock_scanner: MagicMock, issue_registry: IssueRegistry
) -> None:
    """Test that an issue is created when legacy device tracker setup cannot connect."""
    mock_scanner.return_value.get_devices.side_effect = pxssh.ExceptionPxssh("fail")

    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": [{"platform": DOMAIN, **MOCK_CONFIG}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")

    assert len(issue_registry.issues) == 1
    assert issue is not None
    assert issue.translation_key == "yaml_import_cannot_connect"
    assert issue.translation_placeholders == {"host": MOCK_HOST}


def test_scanner_parses_arp_output() -> None:
    """Test that the ARP output parsing only returns recently seen devices."""
    with patch(
        "homeassistant.components.cisco_ios.coordinator.pxssh.pxssh"
    ) as mock_pxssh:
        mock_pxssh.return_value.before = ARP_OUTPUT
        scanner = CiscoIOSArpScanner(
            host=MOCK_HOST, username="admin", password="password", port=22
        )
        devices = scanner.get_devices()

    assert devices == {"00:1D:EC:02:07:AB": "192.168.1.100"}
