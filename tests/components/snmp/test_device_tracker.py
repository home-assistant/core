"""Tests for the SNMP device tracker."""

import binascii
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pysnmp.error import PySnmpError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.proto.rfc1905 import EndOfMibView
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import (
    ATTR_IP,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.device_tracker.const import CONF_CONSIDER_HOME
from homeassistant.components.snmp.const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.snmp.coordinator import MAX_CONSECUTIVE_FAILURES
from homeassistant.const import (
    CONF_HOST,
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

from . import mock_entry, patch_walk

MAC = "00:11:22:33:44:55"
MAC2 = "aa:bb:cc:dd:ee:ff"

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
def enable_tracker(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> Callable[[str], None]:
    """Return a helper which enables a tracker before the platform adds it.

    ScannerEntity creates its entities disabled, so a test which wants a state has
    to have the registry entry in place before the platform adds the entity.
    """

    def _enable(mac: str) -> None:
        (entry,) = hass.config_entries.async_entries(DOMAIN)
        subentry_id = next(iter(entry.subentries))
        entity_registry.async_get_or_create(
            DEVICE_TRACKER_DOMAIN,
            DOMAIN,
            f"{subentry_id}_{mac}",
            config_entry=entry,
            config_subentry_id=subentry_id,
            suggested_object_id=mac,
            disabled_by=None,
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


def _yaml_config(**overrides: Any) -> dict[str, Any]:
    """Return a legacy YAML device tracker config for the ARP table."""
    return {
        DEVICE_TRACKER_DOMAIN: {
            CONF_PLATFORM: "snmp",
            CONF_HOST: "192.168.1.1",
            CONF_COMMUNITY: "public",
            CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2",
            **overrides,
        }
    }


@pytest.mark.parametrize(
    "credentials",
    [
        pytest.param({}, id="community"),
        pytest.param({CONF_AUTH_KEY: "auth", CONF_PRIV_KEY: "priv"}, id="keys"),
    ],
)
async def test_yaml_device_tracker_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
    credentials: dict[str, str],
) -> None:
    """Test that the YAML platform tracks a device and raises the removal repair."""
    # The legacy platform stores the devices it tracks in known_devices.yaml
    hass.config.config_dir = str(tmp_path)
    mac_bytes = binascii.unhexlify("001122334455")
    not_an_address = Mock()
    not_an_address.asOctets.side_effect = AttributeError

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield (
            None,
            None,
            None,
            [
                (Mock(), OctetString(mac_bytes)),
                (Mock(), not_an_address),
            ],
        )

    with patch(
        "homeassistant.components.snmp.device_tracker.bulk_walk_cmd",
        side_effect=mock_walk,
    ):
        assert await async_setup_component(
            hass, DEVICE_TRACKER_DOMAIN, _yaml_config(**credentials)
        )
        await hass.async_block_till_done()

    # The row which is not an address is skipped, so the table holds one device
    assert len(hass.states.async_all(DEVICE_TRACKER_DOMAIN)) == 1
    state = hass.states.get("device_tracker.00_11_22_33_44_55")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == MAC

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_device_tracker")
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_device_tracker"
    assert issue.breaks_in_ha_version == "2027.5.0"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_yaml_device_tracker_unreachable_host(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
) -> None:
    """Test that a host which is neither IPv4 nor IPv6 still raises the repair."""
    hass.config.config_dir = str(tmp_path)
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
        await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, _yaml_config())
        await hass.async_block_till_done()

    assert hass.states.async_all(DEVICE_TRACKER_DOMAIN) == []
    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_device_tracker")
        is not None
    )


def _error_status() -> Mock:
    """Return an SNMP error status."""
    errstatus = Mock()
    errstatus.prettyPrint.return_value = "authorizationError"
    return errstatus


@pytest.mark.parametrize(
    "walk_result",
    [
        pytest.param((errind.requestTimedOut, None, None), id="errindication"),
        pytest.param((None, _error_status(), 0), id="errstatus"),
    ],
)
async def test_yaml_device_tracker_failed_poll(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
    freezer: FrozenDateTimeFactory,
    walk_result: tuple[Any, Any, Any],
) -> None:
    """Test that a poll which fails drops the devices of the table."""
    hass.config.config_dir = str(tmp_path)
    mac_bytes = binascii.unhexlify("001122334455")

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(Mock(), OctetString(mac_bytes))]

    async def mock_failed_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield (*walk_result, [])

    # The scanner walks once to validate the target and once per poll
    with patch(
        "homeassistant.components.snmp.device_tracker.bulk_walk_cmd",
        side_effect=[mock_walk(), mock_walk(), mock_failed_walk()],
    ):
        assert await async_setup_component(
            hass, DEVICE_TRACKER_DOMAIN, _yaml_config(**{CONF_CONSIDER_HOME: 0})
        )
        await hass.async_block_till_done()
        state = hass.states.get("device_tracker.00_11_22_33_44_55")
        assert state is not None and state.state == STATE_HOME

        await _async_advance_poll(hass, freezer)

    state = hass.states.get("device_tracker.00_11_22_33_44_55")
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_device_tracker")
        is not None
    )


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

    oid1 = Mock()
    oid1.asTuple.return_value = _arp_oid(192, 168, 1, 1)
    oid2 = Mock()
    oid2.asTuple.return_value = _arp_oid(192, 168, 1, 22)

    async def mock_walk_1(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid1, OctetString(mac1))]

    async def mock_walk_2(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid2, OctetString(mac2))]

    mock_walk.side_effect = mock_walk_1
    enable_tracker(MAC)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id_1 = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id_1 is not None
    assert hass.states.get(entity_id_1).state == STATE_HOME
    assert hass.states.get(entity_id_1).attributes[ATTR_IP] == "192.168.1.1"

    mock_walk.side_effect = mock_walk_2

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # mac2 is a new device, so its entity is disabled
    entity_id_2 = _tracker_entity_id(entity_registry, entry, MAC2)
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
    """Test that the tracked device is linked to the SNMP device."""
    entry = mock_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    snmp_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert snmp_device is not None
    assert not snmp_device.connections

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, MAC), entry.entry_id
    )
    assert device is not None
    assert device.name == MAC
    assert device.via_device_id == snmp_device.id
    assert device.config_subentry_id == next(iter(entry.subentries))

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.device_id == device.id
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

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, []

    with patch_walk(mock_walk):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes.get(ATTR_IP) is None


async def test_device_tracker_update_empty_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_tracker: Callable[[str], None],
    mock_walk: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update with empty data."""
    entry = mock_entry()
    entry.add_to_hass(hass)
    enable_tracker(MAC)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def mock_empty_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        return
        yield  # pylint: disable=unreachable

    mock_walk.side_effect = mock_empty_walk

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    assert coordinator is not None
    assert coordinator.last_update_success

    entity_id = _tracker_entity_id(entity_registry, entry, MAC)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes.get(ATTR_IP) is None


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

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid, OctetString(input_bytes))]

    enable_tracker(expected_mac)

    with patch_walk(mock_walk):
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
            # Some agents include the NetworkAddress choice type in the index
            (*LEGACY_ARP_MAC_OID, 1, 1, 192, 168, 1, 12),
            "192.168.1.12",
            id="rfc1213_network_address_choice",
        ),
        pytest.param(
            (*LEGACY_ARP_MAC_OID, 1, 2, 192, 168, 1, 12),
            None,
            id="rfc1213_not_an_internet_address",
        ),
        pytest.param(
            # ipNetToMediaTable indexes by a plain IpAddress
            (*ARP_MAC_OID, 1, 1, 192, 168, 1, 12),
            None,
            id="ip_net_to_media_extra_component",
        ),
        pytest.param(
            # Bridge forwarding tables are indexed by the MAC, not by an IP
            (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 1, 0, 26, 43, 60, 77, 94),
            None,
            id="mac_indexed_table",
        ),
        pytest.param(_arp_oid(192, 168, 70000, 1), None, id="octet_out_of_range"),
        pytest.param((*ARP_MAC_OID, 1, 192, 168, 1), None, id="missing_octet"),
        pytest.param((1, 2, 3), None, id="oid_too_short"),
    ],
)
async def test_ip_extraction(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
    oid_tuple: tuple[int, ...],
    expected_ip: str | None,
) -> None:
    """Test IP address extraction from OID suffix."""
    mac_bytes = binascii.unhexlify("001122334455")

    oid = Mock()
    oid.asTuple.return_value = oid_tuple

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    enable_tracker(MAC)

    with patch_walk(mock_walk):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes.get(ATTR_IP) == expected_ip


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

    walks = 0

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Yield the MAC once, then fail on every later poll."""
        nonlocal walks
        walks += 1
        if walks == 1:
            yield None, None, None, [(oid, OctetString(mac_bytes))]
        else:
            yield errindication, None, None, []

    enable_tracker(MAC)

    with patch_walk(mock_walk):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_HOME

        # A transient failure keeps the last known state
        await _async_advance_poll(hass, freezer)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_HOME

        # The entity becomes unavailable once the failures pile up
        await _async_advance_poll(hass, freezer, polls=MAX_CONSECUTIVE_FAILURES - 1)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_walk_unknown_context_makes_the_entity_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    enable_tracker: Callable[[str], None],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a missing SNMPv3 context fails the poll instead of being retried."""
    mac_bytes = binascii.unhexlify("001122334455")
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 1)

    walks = 0

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """Yield the MAC once, then report the missing context on every poll."""
        nonlocal walks
        walks += 1
        if walks == 1:
            yield None, None, None, [(oid, OctetString(mac_bytes))]
        else:
            yield errind.ReportPduReceived("1.3.6.1.6.3.12.1.5.0"), None, None, []

    enable_tracker(MAC)

    with patch_walk(mock_walk):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

        entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
        assert entity_id is not None

        # Polling again can not create the context, so no retrying window
        await _async_advance_poll(hass, freezer)

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

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid, OctetString(b"too_short"))]

    with patch_walk(mock_walk):
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

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid, val)]

    with patch_walk(mock_walk):
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
    mac_bytes = binascii.unhexlify("001122334455")
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 1)

    async def mock_walk(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        yield None, None, None, [(oid, OctetString(mac_bytes))]
        yield None, None, None, [(oid, EndOfMibView())]

    enable_tracker(MAC)

    with patch_walk(mock_walk):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _tracker_entity_id(entity_registry, mock_coordinator_entry, MAC)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME

    # The end of MIB stops the walk, it is not a row of the table
    assert len(hass.states.async_all(DEVICE_TRACKER_DOMAIN)) == 1


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_tracker: Callable[[str], None],
    mock_coordinator_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the registry entry and state of a tracked device."""
    enable_tracker(MAC)

    assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_coordinator_entry.entry_id
    )
