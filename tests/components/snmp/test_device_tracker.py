"""Tests for the SNMP device tracker."""

import binascii
from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pysnmp.error import PySnmpError
from pysnmp.proto.rfc1902 import OctetString
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.components.snmp.device_tracker import (
    SnmpTrackerEntity,
    async_setup_scanner,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_walk():
    """Mock bulk_walk_cmd."""

    async def side_effect(*args, **kwargs):
        # Return a list of MAC addresses
        mac1 = binascii.unhexlify("001122334455")
        oid1 = Mock()
        oid1.asTuple.return_value = (1, 192, 168, 1, 1)
        yield None, None, None, [(oid1, OctetString(mac1))]

    with patch(
        "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
        side_effect=side_effect,
    ) as mock:
        yield mock


@pytest.fixture
def mock_get_cmd():
    """Mock get_cmd for host info."""

    async def side_effect(*args, **kwargs):
        return (
            None,
            None,
            None,
            [
                ("oid_descr", OctetString("TestManufacturer TestModel")),
                ("oid_name", OctetString("TestSysName")),
            ],
        )

    with patch(
        "homeassistant.components.snmp.coordinator.get_cmd",
        side_effect=side_effect,
    ) as mock:
        yield mock


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_setup_with_legacy_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of SNMP device tracker with legacy state (migration).

    When a device was previously tracked via known_devices.yaml and has a
    pre-existing state, it should be enabled by default after migration.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    # Simulate a legacy tracked device with existing state
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )

    assert entity_id is not None

    # Entity should be enabled because it was migrated from a legacy state
    ent_entry = entity_registry.async_get(entity_id)
    assert ent_entry is not None
    assert ent_entry.disabled_by is None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "00:11:22:33:44:55"
    assert state.attributes["ip"] == "192.168.1.1"


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_new_entity_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that newly discovered devices are disabled by default.

    When a new MAC is discovered (no legacy state, no pre-existing device),
    the entity should be disabled by default following the freebox/unifi pattern.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )

    assert entity_id is not None

    # Entity should be disabled by default (no legacy state, no device)
    ent_entry = entity_registry.async_get(entity_id)
    assert ent_entry is not None
    assert ent_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # No state should be present since the entity is disabled
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("mock_get_cmd")
async def test_device_tracker_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_walk: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update of SNMP device tracker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    # Simulate mac1 as a legacy tracked device
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    mac1 = binascii.unhexlify("001122334455")
    mac2 = binascii.unhexlify("aabbccddeeff")
    mac1_str = "00:11:22:33:44:55"
    mac2_str = "aa:bb:cc:dd:ee:ff"

    oid1 = Mock()
    oid1.asTuple.return_value = (1, 192, 168, 1, 1)
    oid2 = Mock()
    oid2.asTuple.return_value = (1, 192, 168, 1, 22)

    async def mock_walk_1(*args, **kwargs):
        yield None, None, None, [(oid1, OctetString(mac1))]

    async def mock_walk_2(*args, **kwargs):
        yield None, None, None, [(oid2, OctetString(mac2))]

    mock_walk.side_effect = mock_walk_1

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id_1 = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac1_str
    )
    assert entity_id_1 is not None
    assert hass.states.get(entity_id_1).state == STATE_HOME
    assert hass.states.get(entity_id_1).attributes["ip"] == "192.168.1.1"

    mock_walk.side_effect = mock_walk_2

    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # mac2 is a newly discovered device (no legacy state) → disabled
    entity_id_2 = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac2_str
    )
    assert entity_id_2 is not None

    entry2 = entity_registry.async_get(entity_id_2)
    assert entry2 is not None
    assert entry2.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # mac1 should now be not_home since it's no longer in the walk results
    assert hass.states.get(entity_id_1).state == STATE_NOT_HOME
    # mac2 is disabled so no state
    assert hass.states.get(entity_id_2) is None


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_device_registry_linking(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities and devices are correctly linked in the registry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    mac = "00:11:22:33:44:55"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify Host Device
    host_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert host_device is not None

    # Verify Client Device Linking (it should not exist because device_info was removed)
    client_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
    )
    assert client_device is None

    # Verify Entity Linking
    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.device_id is None
    assert reg_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_name_resolves_to_mac_address(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the entity name resolves to the expected MAC address format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    # Enable entity by setting legacy state
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "00_11_22_33_44_55"


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_enabled_if_device_exists(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an entity is enabled if its device already exists in the registry.

    This verifies the 'or super().entity_registry_enabled_default' logic.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    # Pre-register the device in the registry with a valid config entry
    other_entry = MockConfigEntry(domain="other_integration")
    other_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:55")},
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None

    # Entity should be enabled because the device already existed
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.disabled_by is None


async def test_async_setup_scanner_import(hass: HomeAssistant) -> None:
    """Test that async_setup_scanner triggers an import flow."""
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert await async_setup_scanner(hass, {"host": "1.2.3.4"}, Mock())
        await hass.async_block_till_done()
        mock_init.assert_called_once()
        args, kwargs = mock_init.call_args
        assert args[0] == DOMAIN
        assert kwargs["context"]["source"] == "import"


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_initial_macs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of SNMP device tracker with initial MACs in the registry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    mac = "00:11:22:33:44:55"
    entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac, config_entry=entry
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_properties_empty_coordinator(
    hass: HomeAssistant,
) -> None:
    """Test entity properties when coordinator data is empty."""
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "1.1.1.1"})
    entry.add_to_hass(hass)

    mock_coord = Mock()
    mock_coord.data = {}

    entity = SnmpTrackerEntity(mock_coord, "00:11:22:33:44:55")
    assert not entity.is_connected
    assert entity.ip_address is None


@pytest.mark.usefixtures("mock_walk", "mock_get_cmd")
async def test_device_tracker_state_cleanup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that existing states are cleaned up during setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    mac = "00:11:22:33:44:55"
    reg_entry = entity_registry.async_get_or_create(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac, config_entry=entry
    )

    # Set a state that should be cleaned up
    hass.states.async_set(reg_entry.entity_id, STATE_HOME)

    original_remove = hass.states.async_remove

    def mock_remove_side_effect(self, entity_id, context=None):
        return original_remove(entity_id, context=context)

    with (
        patch(
            "homeassistant.core.StateMachine.async_remove",
            side_effect=mock_remove_side_effect,
            autospec=True,
        ) as mock_remove,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_remove.assert_called_with(hass.states, reg_entry.entity_id)


@pytest.mark.usefixtures("mock_get_cmd")
async def test_device_tracker_update_empty_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_walk: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update with empty data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Trigger update with empty data
    async def mock_empty_walk(*args, **kwargs):
        return
        yield  # pylint: disable=unreachable

    mock_walk.side_effect = mock_empty_walk

    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.runtime_data.last_update_success

    # Entity should still exist in the registry but no new entities created

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None


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


@pytest.mark.parametrize(
    "errindication",
    [
        pytest.param("timeout", id="string_errindication"),
        pytest.param(PySnmpError("Some error"), id="exception_errindication"),
    ],
)
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
