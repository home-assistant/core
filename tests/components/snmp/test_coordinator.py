"""Tests for the SNMP coordinator behavior (tested via integration setup)."""

import binascii
from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pysnmp.error import PySnmpError
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.error import WrongValueError
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_coordinator_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry for coordinator tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)
    return entry


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
@pytest.mark.usefixtures("mock_udp_transport")
async def test_mac_normalization(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    input_bytes: bytes,
    expected_mac: str,
) -> None:
    """Test MAC address normalization with various formats."""
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 10)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(input_bytes))]

    # Enable the entity by simulating a legacy state
    entity_slug = expected_mac.replace(":", "_").lower()
    hass.states.async_set(f"device_tracker.{entity_slug}", STATE_HOME)

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, expected_mac
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.parametrize(
    ("oid_tuple", "expected_ip"),
    [
        pytest.param(
            (1, 3, 6, 1, 2, 1, 4, 22, 1, 6, 1, 192, 168, 1, 10),
            "192.168.1.10",
            id="full_oid",
        ),
        pytest.param((1, 1, 1, 1, 10, 20, 30, 40), "10.20.30.40", id="short_oid"),
    ],
)
@pytest.mark.usefixtures("mock_udp_transport")
async def test_ip_extraction(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    oid_tuple: tuple,
    expected_ip: str,
) -> None:
    """Test IP address extraction from OID suffix."""
    mac_bytes = binascii.unhexlify("001122334455")
    mac_str = "00:11:22:33:44:55"

    oid = Mock()
    oid.asTuple.return_value = oid_tuple

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    # Enable entity
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac_str
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["ip"] == expected_ip


@pytest.mark.usefixtures("mock_udp_transport")
async def test_ip_extraction_oid_too_short(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that IP is None when OID is too short."""
    mac_bytes = binascii.unhexlify("001122334455")

    oid = Mock()
    oid.asTuple.return_value = (1, 2, 3)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    # Enable entity
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("ip") is None


@pytest.mark.usefixtures("mock_udp_transport")
async def test_walk_error_makes_entry_unavailable(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that a PySnmpError during walk makes the coordinator report failure."""

    async def mock_walk_error(*args, **kwargs):
        raise PySnmpError("Network unreachable")
        yield  # pylint: disable=unreachable

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk_error,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "errindication",
    [
        pytest.param("timeout", id="string_errindication"),
        pytest.param(PySnmpError("Some error"), id="exception_errindication"),
    ],
)
@pytest.mark.usefixtures("mock_udp_transport")
async def test_walk_errindication(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    errindication: str | PySnmpError,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an errindication during walk causes entity to become unavailable."""
    mac_bytes = binascii.unhexlify("001122334455")
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 1)

    async def mock_walk_first(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    async def mock_walk_error(*args, **kwargs):
        yield errindication, None, None, []

    call_count = 0

    async def mock_walk_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            async for item in mock_walk_first(*args, **kwargs):
                yield item
        else:
            async for item in mock_walk_error(*args, **kwargs):
                yield item

    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk_side_effect,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

        # First poll succeeded - entity should be home

        entity_id = entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_HOME

        # Trigger second poll with errindication
        freezer.tick(timedelta(seconds=20))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Entity should become unavailable due to UpdateFailed
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("mock_udp_transport")
async def test_walk_errstatus(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that errstatus during walk causes UpdateFailed."""
    mock_err_status = Mock()
    mock_err_status.prettyPrint.return_value = "noSuchName"

    async def mock_walk(*args, **kwargs):
        yield None, mock_err_status, 1, [("oid", "val")]

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_udp_transport")
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

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    # No entity should be created for invalid MAC

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_coordinator_entry.entry_id
    )
    assert len(entries) == 0


@pytest.mark.usefixtures("mock_udp_transport")
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

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_coordinator_entry.entry_id
    )
    assert len(entries) == 0


@pytest.mark.usefixtures("mock_udp_transport")
async def test_host_info_populates_device_registry(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that host info is fetched and populates the device registry."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Cisco IOS 15.1"), ("oid2", "router01")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    dr_reg = dr.async_get(hass)
    device = dr_reg.async_get_device(
        identifiers={(DOMAIN, mock_coordinator_entry.entry_id)}
    )
    assert device is not None
    assert device.manufacturer == "Cisco"
    assert device.model == "IOS 15.1"
    assert device.name == "router01"


@pytest.mark.usefixtures("mock_udp_transport")
async def test_host_info_no_space_in_descr(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test host info when sysDescr has no spaces."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "SingleWordDescr"), ("oid2", "myhost")],
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    dr_reg = dr.async_get(hass)
    device = dr_reg.async_get_device(
        identifiers={(DOMAIN, mock_coordinator_entry.entry_id)}
    )
    assert device is not None
    assert device.manufacturer is None
    assert device.model == "SingleWordDescr"


@pytest.mark.usefixtures("mock_udp_transport")
async def test_host_info_pysnmp_error_sets_empty_model(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that a PySnmpError during host info fetch prevents re-fetching."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            side_effect=PySnmpError("Connection timed out"),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    dr_reg = dr.async_get(hass)
    device = dr_reg.async_get_device(
        identifiers={(DOMAIN, mock_coordinator_entry.entry_id)}
    )
    assert device is not None
    assert device.model == ""


@pytest.mark.usefixtures("mock_udp_transport")
async def test_host_info_errstatus_sets_generic_name(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that get_cmd with errindication/errstatus sets a generic model name."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=("some error indication", None, None, []),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    dr_reg = dr.async_get(hass)
    device = dr_reg.async_get_device(
        identifiers={(DOMAIN, mock_coordinator_entry.entry_id)}
    )
    assert device is not None
    assert device.model == "SNMP Server"


@pytest.mark.usefixtures("mock_udp_transport")
async def test_host_info_auth_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that WrongValueError during host info get_cmd triggers reauth."""

    async def mock_walk(*args, **kwargs):
        return
        yield

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            side_effect=WrongValueError,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_host_info_request_args_wrong_value_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test WrongValueError raised by _async_ensure_request_args during host info."""
    with (
        patch(
            "homeassistant.components.snmp.coordinator.async_create_request_cmd_args",
            side_effect=WrongValueError,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_update_data_request_args_wrong_value_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test WrongValueError raised by _async_ensure_request_args during update.

    Host info succeeds via the PySnmpError fallback (sets model=''), then
    _async_ensure_request_args is called again in _async_update_data and raises
    WrongValueError, triggering ConfigEntryAuthFailed.
    """
    call_count = 0

    async def mock_create_request_args_side(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PySnmpError("First call fails")
        raise WrongValueError

    with (
        patch(
            "homeassistant.components.snmp.coordinator.create_auth_data",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.async_create_request_cmd_args",
            side_effect=mock_create_request_args_side,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


async def test_update_data_request_args_pysnmp_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test PySnmpError raised by _async_ensure_request_args during update.

    Host info succeeds via the PySnmpError fallback (sets model=''), then
    _async_ensure_request_args is called again in _async_update_data and raises
    PySnmpError, triggering UpdateFailed.
    """

    async def mock_create_request_args_fail(*args, **kwargs):
        raise PySnmpError("Always fails")

    with (
        patch(
            "homeassistant.components.snmp.coordinator.create_auth_data",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.async_create_request_cmd_args",
            side_effect=mock_create_request_args_fail,
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_udp_transport")
async def test_walk_auth_error(
    hass: HomeAssistant,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that WrongValueError during walk triggers reauth."""
    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=WrongValueError,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
    ):
        assert not await hass.config_entries.async_setup(
            mock_coordinator_entry.entry_id
        )
        await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_udp_transport")
async def test_walk_end_of_mib(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
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

    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)
    hass.states.async_set("device_tracker.aa_bb_cc_dd_ee_ff", STATE_HOME)

    with (
        patch(
            "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(
                None,
                None,
                None,
                [("oid1", "Manufacturer Model"), ("oid2", "SysName")],
            ),
        ),
        patch(
            "homeassistant.components.snmp.coordinator.is_end_of_mib",
            side_effect=[False, True],
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    # First MAC should have been processed (is_end_of_mib returned False)
    entity_id_1 = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id_1 is not None
    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.state == STATE_HOME

    # Second MAC should NOT have been processed (is_end_of_mib returned True)
    entity_id_2 = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "aa:bb:cc:dd:ee:ff"
    )
    assert entity_id_2 is None
