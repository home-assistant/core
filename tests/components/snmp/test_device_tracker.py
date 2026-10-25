"""Tests for the SNMP device tracker."""

import binascii
from collections.abc import Callable, Iterator
from itertools import cycle
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pysnmp.error import PySnmpError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.components.snmp.coordinator import MAX_CONSECUTIVE_FAILURES
from homeassistant.components.snmp.device_tracker import (
    SnmpScanner,
    SnmpTrackerEntity,
    async_get_scanner,
)
from homeassistant.const import (
    CONF_PLATFORM,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import mock_entry

MAC = "00:11:22:33:44:55"

# ipNetToMediaPhysAddress, the MAC column of the ARP table
ARP_MAC_OID = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2)

# atPhysAddress, the MAC column of the deprecated RFC 1213 ARP table
LEGACY_ARP_MAC_OID = (1, 3, 6, 1, 2, 1, 3, 1, 1, 2)


def _arp_oid(*octets: int) -> tuple[int, ...]:
    """Return the OID of an ARP table row for the given IPv4 octets."""
    return (*ARP_MAC_OID, 1, *octets)


async def _async_advance_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, polls: int = 1
) -> None:
    """Advance the given number of polls, one by default."""
    for _ in range(polls):
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


@pytest.fixture
def mock_walk() -> Iterator[Mock]:
    """Mock bulk_walk_cmd."""

    async def side_effect(*args, **kwargs):
        # Return a list of MAC addresses
        mac1 = binascii.unhexlify("001122334455")
        oid1 = Mock()
        oid1.asTuple.return_value = _arp_oid(192, 168, 1, 1)
        yield None, None, None, [(oid1, OctetString(mac1))]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=side_effect,
    ) as mock:
        yield mock


@pytest.fixture
def enable_tracker(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> Callable[[str], None]:
    """Return a helper which makes a tracker enabled by registering its MAC."""

    def _enable(mac: str) -> None:
        other_entry = MockConfigEntry(domain="other_integration")
        other_entry.add_to_hass(hass)
        device_registry.async_get_or_create(
            config_entry_id=other_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        )

    return _enable


def _tracker_entity_id(
    ent_reg: er.EntityRegistry, entry: MockConfigEntry, mac: str
) -> str | None:
    """Return the entity id of a tracker of the entry's only subentry."""
    subentry_id = next(iter(entry.subentries))
    return ent_reg.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, f"{subentry_id}_{mac}"
    )


@pytest.fixture
def mock_coordinator_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry for coordinator tests."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    return entry


async def test_yaml_device_tracker_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that the YAML platform still works and raises the removal repair."""
    config = {
        DEVICE_TRACKER_DOMAIN: {
            CONF_PLATFORM: "snmp",
            "host": "192.168.1.1",
            "community": "public",
            "baseoid": "1.3.6.1.2.1.4.22.1.2",
        }
    }

    async def mock_walk(*args, **kwargs):
        yield None, None, None, []

    with patch(
        "homeassistant.components.snmp.device_tracker.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, config)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_device_tracker")
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_device_tracker"
    assert issue.breaks_in_ha_version == "2027.5.0"
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_new_entity_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that newly discovered devices are disabled by default.

    When a new MAC is discovered (no pre-existing device), the entity should be
    disabled by default following the freebox/unifi pattern.
    """
    entry = mock_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)

    assert entity_id is not None

    ent_entry = entity_registry.async_get(entity_id)
    assert ent_entry is not None
    assert ent_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # No state should be present since the entity is disabled
    assert hass.states.get(entity_id) is None


async def test_device_tracker_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_tracker: Callable[[str], None],
    mock_walk: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update of SNMP device tracker."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    mac1 = binascii.unhexlify("001122334455")
    mac2 = binascii.unhexlify("aabbccddeeff")
    mac1_str = "00:11:22:33:44:55"
    mac2_str = "aa:bb:cc:dd:ee:ff"

    oid1 = Mock()
    oid1.asTuple.return_value = _arp_oid(192, 168, 1, 1)
    oid2 = Mock()
    oid2.asTuple.return_value = _arp_oid(192, 168, 1, 22)

    async def mock_walk_1(*args, **kwargs):
        yield None, None, None, [(oid1, OctetString(mac1))]

    async def mock_walk_2(*args, **kwargs):
        yield None, None, None, [(oid2, OctetString(mac2))]

    mock_walk.side_effect = mock_walk_1
    enable_tracker(mac1_str)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id_1 = _tracker_entity_id(entity_registry, entry, mac1_str)
    assert entity_id_1 is not None
    assert hass.states.get(entity_id_1).state == STATE_HOME
    assert hass.states.get(entity_id_1).attributes["ip"] == "192.168.1.1"

    mock_walk.side_effect = mock_walk_2

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # mac2 is a new device, so its entity is disabled
    entity_id_2 = _tracker_entity_id(entity_registry, entry, mac2_str)
    assert entity_id_2 is not None

    entry2 = entity_registry.async_get(entity_id_2)
    assert entry2 is not None
    assert entry2.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # mac1 should now be not_home since it's no longer in the walk results
    assert hass.states.get(entity_id_1).state == STATE_NOT_HOME
    # mac2 is disabled so no state
    assert hass.states.get(entity_id_2) is None


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_device_registry_linking(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the tracker entity is not linked to a device."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    mac = "00:11:22:33:44:55"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
        )
        is None
    )

    entity_id = _tracker_entity_id(entity_registry, entry, mac)
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.device_id is None
    assert reg_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_name_resolves_to_mac_address(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_tracker: Callable[[str], None],
) -> None:
    """Test that the entity name resolves to the expected MAC address format."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    enable_tracker(MAC)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == MAC


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_enabled_if_device_exists(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an entity is enabled if its device already exists in the registry.

    ScannerEntity only enables new entities when a device with the same MAC is
    already known to Home Assistant.
    """
    entry = mock_entry()
    entry.add_to_hass(hass)

    other_entry = MockConfigEntry(domain="other_integration")
    other_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC)},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id is not None

    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.disabled_by is None


async def test_device_tracker_initial_macs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that previously known MACs show up as not_home without a walk row."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    subentry_id = next(iter(entry.subentries))
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN,
        DOMAIN,
        f"{subentry_id}_{MAC}",
        config_entry=entry,
        config_subentry_id=subentry_id,
    )

    async def mock_walk(*args, **kwargs):
        yield None, None, None, []

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME


async def test_device_tracker_properties_empty_coordinator() -> None:
    """Test entity properties when coordinator data is empty."""
    mock_coord = Mock()
    mock_coord.data = {}

    entity = SnmpTrackerEntity(mock_coord, MAC)
    assert not entity.is_connected
    assert entity.ip_address is None


async def test_device_tracker_update_empty_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_walk: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update with empty data."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def mock_empty_walk(*args, **kwargs):
        return
        yield  # pylint: disable=unreachable

    mock_walk.side_effect = mock_empty_walk

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    assert coordinator.last_update_success

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id is not None


@pytest.mark.parametrize(
    ("input_bytes", "expected_mac"),
    [
        pytest.param(
            binascii.unhexlify("001122334455"), "00:11:22:33:44:55", id="binary"
        ),
        pytest.param(b"00:11:22:33:44:66", "00:11:22:33:44:66", id="colon_string"),
        pytest.param(b"00-11-22-33-44-77", "00:11:22:33:44:77", id="dash_string"),
        pytest.param(b"0011.2233.4488", "00:11:22:33:44:88", id="dot_string"),
        pytest.param(b"00 11 22 33 44 99", "00:11:22:33:44:99", id="space_string"),
        pytest.param(b"ABCDEFABCDEF", "ab:cd:ef:ab:cd:ef", id="raw_hex_string"),
    ],
)
async def test_mac_normalization(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
    input_bytes: bytes,
    expected_mac: str,
) -> None:
    """Test MAC address normalization with various formats."""
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 10)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(input_bytes))]

    enable_tracker(expected_mac)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(
        entity_registry, mock_coordinator_entry, expected_mac
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.parametrize(
    ("oid_tuple", "expected_ip"),
    [
        pytest.param(_arp_oid(192, 168, 1, 10), "192.168.1.10", id="arp_row"),
        pytest.param(
            (*LEGACY_ARP_MAC_OID, 1, 192, 168, 1, 11),
            "192.168.1.11",
            id="rfc1213_arp_row",
        ),
        pytest.param(
            # Bridge forwarding tables are indexed by the MAC, not by an IP
            (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 1, 0, 26, 43, 60, 77, 94),
            None,
            id="mac_indexed_table",
        ),
        pytest.param(_arp_oid(192, 168, 70000, 1), None, id="octet_out_of_range"),
        pytest.param((*ARP_MAC_OID, 1, 192, 168, 1), None, id="missing_octet"),
    ],
)
async def test_ip_extraction(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
    oid_tuple: tuple,
    expected_ip: str,
) -> None:
    """Test IP address extraction from OID suffix."""
    mac_bytes = binascii.unhexlify("001122334455")
    mac_str = MAC

    oid = Mock()
    oid.asTuple.return_value = oid_tuple

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    enable_tracker(mac_str)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, mac_str)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes.get("ip") == expected_ip


async def test_ip_extraction_oid_too_short(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
) -> None:
    """Test that IP is None when OID is too short."""
    mac_bytes = binascii.unhexlify("001122334455")

    oid = Mock()
    oid.asTuple.return_value = (1, 2, 3)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    enable_tracker(MAC)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes.get("ip") is None


@pytest.mark.parametrize(
    "errindication",
    [
        pytest.param(errind.requestTimedOut, id="timeout"),
        pytest.param(PySnmpError("Some error"), id="exception"),
    ],
)
async def test_walk_errindication(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
    errindication: errind.ErrorIndication | PySnmpError,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that repeated errindications make the entity unavailable."""
    mac_bytes = binascii.unhexlify("001122334455")
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 1)

    async def mock_walk_first(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    async def mock_walk_error(*args, **kwargs):
        yield errindication, None, None, []

    fail = False

    async def mock_walk_side_effect(*args, **kwargs):
        walk = mock_walk_error if fail else mock_walk_first
        async for item in walk(*args, **kwargs):
            yield item

    enable_tracker(MAC)

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk_side_effect,
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_HOME

        # A transient failure keeps the last known state
        fail = True
        await _async_advance_poll(hass, freezer)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_HOME

        # The entity becomes unavailable once the failures pile up
        await _async_advance_poll(hass, freezer, polls=MAX_CONSECUTIVE_FAILURES - 1)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_invalid_mac_length_ignored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that MAC addresses with invalid length are ignored."""
    oid = Mock()
    oid.asTuple.return_value = (1, 1, 1, 1, 0)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(b"too_short"))]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_coordinator_entry.entry_id
    )
    assert len(entries) == 0


async def test_mac_processing_exception_ignored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that exceptions during MAC processing are silently ignored."""
    oid = Mock()
    oid.asTuple.return_value = (1, 1, 1, 1, 0)
    val = Mock()
    val.asOctets.side_effect = AttributeError

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, val)]

    with patch(
        "homeassistant.components.snmp.client.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_coordinator_entry.entry_id
    )
    assert len(entries) == 0


async def test_walk_end_of_mib(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
) -> None:
    """Test that walk stops when end of MIB is reached."""
    mac1_bytes = binascii.unhexlify("001122334455")
    mac2_bytes = binascii.unhexlify("aabbccddeeff")
    oid1 = Mock()
    oid1.asTuple.return_value = (1, 192, 168, 1, 1)
    oid2 = Mock()
    oid2.asTuple.return_value = (1, 192, 168, 1, 2)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid1, OctetString(mac1_bytes))]
        yield None, None, None, [(oid2, OctetString(mac2_bytes))]

    enable_tracker(MAC)

    with (
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.client.is_end_of_mib",
            side_effect=cycle((False, True)),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    # First MAC should have been processed (is_end_of_mib returned False)
    entity_id_1 = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
    assert entity_id_1 is not None
    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.state == STATE_HOME

    # Second MAC should NOT have been processed (is_end_of_mib returned True)
    entity_id_2 = _tracker_entity_id(
        entity_registry, mock_coordinator_entry, "aa:bb:cc:dd:ee:ff"
    )
    assert entity_id_2 is None


def _scanner_config(**overrides: str) -> dict:
    """Return a YAML device tracker config for the scanner."""
    return {
        DEVICE_TRACKER_DOMAIN: {
            CONF_PLATFORM: "snmp",
            "host": "192.168.1.1",
            "community": "public",
            "baseoid": "1.3.6.1.2.1.4.22.1.2",
            **overrides,
        }
    }


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="community"),
        pytest.param({"auth_key": "auth"}, id="auth_only"),
        pytest.param({"auth_key": "auth", "priv_key": "priv"}, id="auth_and_priv"),
    ],
)
def test_scanner_auth_data(overrides: dict[str, str]) -> None:
    """Test scanner creation for the supported credential combinations."""
    config = _scanner_config(**overrides)[DEVICE_TRACKER_DOMAIN]
    scanner = SnmpScanner(config)
    assert scanner.baseoid == "1.3.6.1.2.1.4.22.1.2"
    assert scanner.success_init is False


def test_scanner_privacy_without_auth_raises() -> None:
    """Test that a privacy key without an authentication key is rejected."""
    config = _scanner_config(priv_key="priv")[DEVICE_TRACKER_DOMAIN]
    with pytest.raises(PySnmpError):
        SnmpScanner(config)


async def test_scanner_create_ipv6_fallback() -> None:
    """Test that an IPv4 failure falls back to IPv6."""
    config = _scanner_config()[DEVICE_TRACKER_DOMAIN]
    with (
        patch(
            "homeassistant.components.snmp.device_tracker.UdpTransportTarget.create",
            side_effect=PySnmpError("no ipv4"),
        ),
        patch(
            "homeassistant.components.snmp.device_tracker.Udp6TransportTarget",
            return_value=Mock(),
        ),
    ):
        scanner = await SnmpScanner.create(config)

    assert scanner is not None


async def test_scanner_create_invalid_host() -> None:
    """Test that an unreachable host yields no scanner."""
    config = _scanner_config()[DEVICE_TRACKER_DOMAIN]
    with (
        patch(
            "homeassistant.components.snmp.device_tracker.UdpTransportTarget.create",
            side_effect=PySnmpError("no ipv4"),
        ),
        patch(
            "homeassistant.components.snmp.device_tracker.Udp6TransportTarget",
            side_effect=PySnmpError("no ipv6"),
        ),
    ):
        assert await SnmpScanner.create(config) is None


async def test_scanner_scan_devices() -> None:
    """Test the DeviceScanner interface of the legacy scanner."""
    scanner = SnmpScanner(_scanner_config()[DEVICE_TRACKER_DOMAIN])
    scanner.success_init = True
    scanner.last_results = [{"mac": MAC}, {}]

    with patch.object(scanner, "async_get_snmp_data", return_value=[{"mac": MAC}]):
        assert await scanner.async_scan_devices() == [MAC]

    assert await scanner.async_get_device_name(MAC) is None
    assert await scanner.async_get_extra_attributes(MAC) == {"mac": MAC}
    assert await scanner.async_get_extra_attributes("other") == {}


async def test_scanner_update_not_initialized() -> None:
    """Test that an uninitialized scanner reports no devices."""
    scanner = SnmpScanner(_scanner_config()[DEVICE_TRACKER_DOMAIN])
    assert await scanner.async_scan_devices() == []


async def test_scanner_walk_errindication() -> None:
    """Test that a walk error indication yields no data."""
    scanner = SnmpScanner(_scanner_config()[DEVICE_TRACKER_DOMAIN])
    scanner.request_args = (Mock(), Mock(), Mock(), Mock(), Mock())

    async def mock_walk(*args, **kwargs):
        yield errind.requestTimedOut, None, None, []

    with patch(
        "homeassistant.components.snmp.device_tracker.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await scanner.async_get_snmp_data() is None


async def test_scanner_walk_errstatus() -> None:
    """Test that an SNMP error status yields no data."""
    scanner = SnmpScanner(_scanner_config()[DEVICE_TRACKER_DOMAIN])
    scanner.request_args = (Mock(), Mock(), Mock(), Mock(), Mock())
    errstatus = Mock()
    errstatus.prettyPrint.return_value = "authorizationError"

    async def mock_walk(*args, **kwargs):
        yield None, errstatus, 0, []

    with patch(
        "homeassistant.components.snmp.device_tracker.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await scanner.async_get_snmp_data() is None


async def test_scanner_walk_mac() -> None:
    """Test parsing MACs from the walk and skipping unusable values."""
    scanner = SnmpScanner(_scanner_config()[DEVICE_TRACKER_DOMAIN])
    scanner.request_args = (Mock(), Mock(), Mock(), Mock(), Mock())
    bad_value = Mock()
    bad_value.asOctets.side_effect = AttributeError

    async def mock_walk(*args, **kwargs):
        yield (
            None,
            None,
            None,
            [
                (Mock(), OctetString(binascii.unhexlify("001122334455"))),
                (Mock(), bad_value),
            ],
        )

    with (
        patch(
            "homeassistant.components.snmp.device_tracker.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.device_tracker.is_end_of_mib",
            return_value=False,
        ),
    ):
        assert await scanner.async_get_snmp_data() == [{"mac": MAC}]


async def test_async_get_scanner_invalid_host(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that an invalid host returns no scanner but still raises the repair."""
    config = _scanner_config()

    with patch(
        "homeassistant.components.snmp.device_tracker.SnmpScanner.create",
        return_value=None,
    ):
        assert await async_get_scanner(hass, config) is None

    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_device_tracker")
        is not None
    )
