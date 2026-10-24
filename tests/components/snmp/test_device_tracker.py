"""Tests for the SNMP device tracker."""

import binascii
from collections.abc import Iterator
from itertools import cycle
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pysnmp.error import PySnmpError
from pysnmp.proto.rfc1902 import OctetString
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.components.snmp.const import (
    CONF_BASEOID,
    CONF_CONTEXT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from homeassistant.components.snmp.coordinator import MAX_CONSECUTIVE_FAILURES
from homeassistant.components.snmp.device_tracker import (
    SnmpTrackerEntity,
    _async_legacy_tracked_dev_ids,
    _is_migrated_table,
    async_setup_scanner,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PLATFORM,
    CONF_PORT,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import dump

from . import mock_entry

from tests.common import MockConfigEntry, async_fire_time_changed, patch_yaml_files

MAC = "00:11:22:33:44:55"
LEGACY_ENTITY_ID = "device_tracker.00_11_22_33_44_55"

# ipNetToMediaPhysAddress, the MAC column of the ARP table
ARP_MAC_OID = (1, 3, 6, 1, 2, 1, 4, 22, 1, 2)

# atPhysAddress, the MAC column of the deprecated RFC 1213 ARP table
LEGACY_ARP_MAC_OID = (1, 3, 6, 1, 2, 1, 3, 1, 1, 2)


def _arp_oid(*octets: int) -> tuple[int, ...]:
    """Return the OID of an ARP table row for the given IPv4 octets."""
    return (*ARP_MAC_OID, 1, *octets)


def _known_devices(*macs: str) -> dict[str, str]:
    """Return a patched known_devices.yaml that tracks the given MACs."""
    return {
        YAML_DEVICES: dump(
            {mac: {"name": mac, "mac": mac, "track": True} for mac in macs}
        )
    }


def _known_devices_named(dev_id: str, mac: str) -> dict[str, str]:
    """Return a patched known_devices.yaml that names a tracked device.

    The key is the dev_id the legacy tracker turns into the entity id.
    """
    return {YAML_DEVICES: dump({dev_id: {"name": dev_id, "mac": mac, "track": True}})}


async def _async_advance_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, polls: int = 1
) -> None:
    """Advance the given number of polls, one by default.

    The legacy device tracker writes not_home once during setup for the devices it
    loaded from known_devices.yaml and never saw, and that write can land after the
    new entity wrote its state, so tests assert after a poll of the tracker.
    """
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


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_legacy_state_is_not_an_enable_signal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a leftover legacy state does not enable an entity.

    The legacy YAML tracker writes its states only after this entry has been set
    up, so such a state is not a sign that the device was tracked; known_devices.yaml
    is. This entry is not an import either, so its entities stay disabled.
    """
    entry = mock_entry()
    entry.add_to_hass(hass)

    hass.states.async_set(LEGACY_ENTITY_ID, STATE_HOME)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
    assert entity_id is not None
    assert entity_id != LEGACY_ENTITY_ID

    ent_entry = entity_registry.async_get(entity_id)
    assert ent_entry is not None
    assert ent_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # The state belongs to the legacy tracker, so it is left alone
    assert hass.states.get(LEGACY_ENTITY_ID) is not None


@pytest.mark.usefixtures("mock_walk")
async def test_yaml_migration_keeps_entity_enabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Migrate a YAML device tracker without disabling its entity.

    Exercises the path an upgrading user actually takes: the legacy platform in
    configuration.yaml is set up, which triggers the import flow, which sets up the
    config entry. The legacy integration only writes the states of the devices it
    tracks after that point, so known_devices.yaml is what keeps them enabled.
    """
    config = {
        DEVICE_TRACKER_DOMAIN: {
            CONF_PLATFORM: "snmp",
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.2",
            "community": "public",
        }
    }

    with patch_yaml_files(_known_devices(MAC)):
        assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, config)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT

    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
    assert entity_id == LEGACY_ENTITY_ID

    ent_entry = entity_registry.async_get(entity_id)
    assert ent_entry is not None

    # A migrated entity that ends up disabled silently breaks the presence
    # automations of the user who is upgrading.
    assert ent_entry.disabled_by is None

    # The entity must be live, not merely enabled in the registry
    assert hass.states.get(LEGACY_ENTITY_ID) is not None


@pytest.mark.usefixtures("mock_walk")
async def test_yaml_migration_keeps_named_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Migrate a named YAML device while keeping its custom entity id.

    known_devices.yaml keys become the legacy entity ids, so a device the user
    named must keep device_tracker.<dev_id> instead of getting the MAC form.
    """
    config = {
        DEVICE_TRACKER_DOMAIN: {
            CONF_PLATFORM: "snmp",
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.2",
            "community": "public",
        }
    }

    with patch_yaml_files(_known_devices_named("andrea_phone", MAC)):
        assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, config)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT

    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
        == "device_tracker.andrea_phone"
    )


@pytest.mark.usefixtures("mock_walk")
async def test_yaml_migration_named_entity_id_collision_is_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Report a named device whose custom entity id was claimed by another entity."""
    entry = mock_entry(source=SOURCE_IMPORT)
    entry.add_to_hass(hass)

    hass.states.async_set("device_tracker.andrea_phone", STATE_HOME)

    with patch_yaml_files(_known_devices_named("andrea_phone", MAC)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
    assert entity_id is not None
    assert entity_id != "device_tracker.andrea_phone"

    issue = issue_registry.async_get_issue(DOMAIN, f"entity_id_changed_{MAC}")
    assert issue is not None
    assert issue.translation_placeholders == {
        "mac": MAC,
        "entity_id": "device_tracker.andrea_phone",
        "new_entity_id": entity_id,
    }


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_new_entity_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that newly discovered devices are disabled by default.

    When a new MAC is discovered (no legacy state, no pre-existing device),
    the entity should be disabled by default following the freebox/unifi pattern.
    """
    entry = mock_entry()
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


async def test_device_tracker_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_walk: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update of SNMP device tracker."""
    entry = mock_entry(source=SOURCE_IMPORT)
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

    # mac1 was tracked by the legacy YAML configuration
    with patch_yaml_files(_known_devices(mac1_str)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await _async_advance_poll(hass, freezer)

    entity_id_1 = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac1_str
    )
    assert entity_id_1 is not None
    assert hass.states.get(entity_id_1).state == STATE_HOME
    assert hass.states.get(entity_id_1).attributes["ip"] == "192.168.1.1"

    mock_walk.side_effect = mock_walk_2

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # mac2 is not tracked by the legacy YAML configuration, so it is a new device
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

    # The entry creates no device of its own, and ScannerEntity does not create
    # one for the MAC either
    assert not dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
        )
        is None
    )

    # Verify Entity Linking
    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
    reg_entry = entity_registry.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.device_id is None
    assert reg_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_name_resolves_to_mac_address(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the entity name resolves to the expected MAC address format."""
    entry = mock_entry(source=SOURCE_IMPORT)
    entry.add_to_hass(hass)

    # The device was tracked by the legacy YAML configuration
    with patch_yaml_files(_known_devices(MAC)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "00:11:22:33:44:55"


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


@pytest.mark.usefixtures("mock_walk")
async def test_async_setup_scanner_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a YAML configuration without v3 keys is imported."""
    assert (
        await async_setup_scanner(
            hass,
            {
                CONF_PLATFORM: DOMAIN,
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.2.1.4.22.1.2",
                "community": "public",
            },
            Mock(),
        )
        is True
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"


@pytest.mark.usefixtures("mock_walk")
async def test_async_setup_scanner_second_table_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a second YAML tracker for the same host is not dropped silently."""
    config = {
        CONF_PLATFORM: DOMAIN,
        "host": "192.168.1.1",
        "baseoid": "1.3.6.1.2.1.4.22.1.2",
        "community": "public",
    }
    assert await async_setup_scanner(hass, config, Mock()) is True
    await hass.async_block_till_done()

    baseoid = "1.3.6.1.2.1.17.4.3.1.2"
    assert (
        await async_setup_scanner(hass, {**config, "baseoid": baseoid}, Mock()) is False
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"deprecated_yaml_import_issue_multiple_trackers_192.168.1.1_{baseoid}",
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_import_issue_multiple_trackers"
    assert issue.translation_placeholders == {
        "integration_title": "SNMP",
        "host": "192.168.1.1",
        "baseoid": baseoid,
    }


@pytest.mark.usefixtures("mock_walk")
async def test_async_setup_scanner_same_table_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that re-importing the same table is not reported as a lost tracker."""
    config = {
        CONF_PLATFORM: DOMAIN,
        "host": "192.168.1.1",
        "baseoid": "1.3.6.1.2.1.4.22.1.2",
        "community": "public",
    }
    issue_id = (
        "deprecated_yaml_import_issue_multiple_trackers_"
        "192.168.1.1_1.3.6.1.2.1.4.22.1.2"
    )
    assert await async_setup_scanner(hass, config, Mock()) is True
    await hass.async_block_till_done()

    # A restart re-imports the block, so a stale report has to be cleaned up
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml_import_issue_multiple_trackers",
        translation_placeholders={
            "integration_title": "SNMP",
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.2",
        },
    )
    assert await async_setup_scanner(hass, config, Mock()) is True
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("host", "port"),
    [
        pytest.param("192.168.1.2", 161, id="other_host"),
        pytest.param("192.168.1.1", 1161, id="other_port"),
    ],
)
async def test_is_migrated_table_ignores_other_agents(
    hass: HomeAssistant, host: str, port: int
) -> None:
    """Test that an entry for another agent does not count as migrated."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: host, CONF_PORT: port, CONF_CONTEXT_NAME: ""},
        subentries_data=[
            {
                "data": {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"},
                "subentry_type": SUBENTRY_TYPE_DEVICE_TRACKER,
                "title": "Device tracker",
                "unique_id": SUBENTRY_TYPE_DEVICE_TRACKER,
            }
        ],
    ).add_to_hass(hass)

    assert not _is_migrated_table(
        hass,
        {
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 161,
            CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2",
        },
    )


async def test_is_migrated_table_requires_the_default_context(
    hass: HomeAssistant,
) -> None:
    """Test that a table polled through another context is not migrated."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 161,
            CONF_CONTEXT_NAME: "device",
        },
        subentries_data=[
            {
                "data": {CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2"},
                "subentry_type": SUBENTRY_TYPE_DEVICE_TRACKER,
                "title": "Device tracker",
                "unique_id": SUBENTRY_TYPE_DEVICE_TRACKER,
            }
        ],
    ).add_to_hass(hass)

    assert not _is_migrated_table(
        hass,
        {
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 161,
            CONF_BASEOID: "1.3.6.1.2.1.4.22.1.2",
        },
    )


async def test_async_setup_scanner_v3_credentials(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a YAML configuration with v3 credentials is not imported."""
    assert (
        await async_setup_scanner(
            hass,
            {
                CONF_PLATFORM: DOMAIN,
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.2.1.4.22.1.2",
                "auth_key": "auth_key",
                "priv_key": "priv_key",
            },
            Mock(),
        )
        is False
    )

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_credentials_required"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_import_issue_credentials_required"
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "SNMP",
        "host": "192.168.1.1",
    }


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_initial_macs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of SNMP device tracker with initial MACs in the registry."""
    entry = mock_entry()
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


async def test_device_tracker_properties_empty_coordinator() -> None:
    """Test entity properties when coordinator data is empty."""
    mock_coord = Mock()
    mock_coord.data = {}

    entity = SnmpTrackerEntity(mock_coord, "00:11:22:33:44:55")
    assert not entity.is_connected
    assert entity.ip_address is None


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_entity_id_changed_repair(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_coordinator_entry: MockConfigEntry,
) -> None:
    """Test that a migrated entity which lost its entity id is reported."""
    # Another entity already claimed the entity id the migration keeps
    hass.states.async_set(LEGACY_ENTITY_ID, STATE_HOME)

    with patch_yaml_files(_known_devices(MAC)):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
    assert entity_id is not None
    assert entity_id != LEGACY_ENTITY_ID

    issue = issue_registry.async_get_issue(DOMAIN, f"entity_id_changed_{MAC}")
    assert issue is not None
    assert issue.translation_key == "entity_id_changed"
    assert issue.translation_placeholders == {
        "mac": MAC,
        "entity_id": LEGACY_ENTITY_ID,
        "new_entity_id": entity_id,
    }


@pytest.mark.usefixtures("mock_walk")
async def test_device_tracker_entity_id_rename_is_not_reported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that renaming a migrated entity is not reported as a lost id."""
    config = {
        DEVICE_TRACKER_DOMAIN: {
            CONF_PLATFORM: "snmp",
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.2",
            "community": "public",
        }
    }

    with patch_yaml_files(_known_devices_named("andrea_phone", MAC)):
        assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, config)
        await hass.async_block_till_done()

    legacy_entity_id = "device_tracker.andrea_phone"
    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
        == legacy_entity_id
    )

    entity_registry.async_update_entity(
        legacy_entity_id, new_entity_id="device_tracker.renamed"
    )
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch_yaml_files(_known_devices_named("andrea_phone", MAC)):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
        == "device_tracker.renamed"
    )
    assert issue_registry.async_get_issue(DOMAIN, f"entity_id_changed_{MAC}") is None


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

    # Trigger update with empty data
    async def mock_empty_walk(*args, **kwargs):
        return
        yield  # pylint: disable=unreachable

    mock_walk.side_effect = mock_empty_walk

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    assert coordinator.last_update_success

    # Entity should still exist in the registry but no new entities created

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None


@pytest.fixture
def mock_coordinator_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock SNMP config entry for coordinator tests.

    The entry mimics a migration, so the devices listed in known_devices.yaml are
    enabled and the tests can assert on live entities.
    """
    entry = mock_entry(source=SOURCE_IMPORT)
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
    freezer: FrozenDateTimeFactory,
    input_bytes: bytes,
    expected_mac: str,
) -> None:
    """Test MAC address normalization with various formats."""
    oid = Mock()
    oid.asTuple.return_value = (1, 192, 168, 1, 10)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(input_bytes))]

    with (
        patch_yaml_files(_known_devices(expected_mac)),
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()
        await _async_advance_poll(hass, freezer)

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
    oid_tuple: tuple,
    expected_ip: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test IP address extraction from OID suffix."""
    mac_bytes = binascii.unhexlify("001122334455")
    mac_str = "00:11:22:33:44:55"

    oid = Mock()
    oid.asTuple.return_value = oid_tuple

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    with (
        patch_yaml_files(_known_devices(mac_str)),
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()
        await _async_advance_poll(hass, freezer)

    entity_id = entity_registry.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, mac_str
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes.get("ip") == expected_ip


async def test_ip_extraction_oid_too_short(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_coordinator_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that IP is None when OID is too short."""
    mac_bytes = binascii.unhexlify("001122334455")

    oid = Mock()
    oid.asTuple.return_value = (1, 2, 3)

    async def mock_walk(*args, **kwargs):
        yield None, None, None, [(oid, OctetString(mac_bytes))]

    with (
        patch_yaml_files(_known_devices(MAC)),
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()
        await _async_advance_poll(hass, freezer)

    entity_id = entity_registry.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, MAC)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
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

    with (
        patch_yaml_files(_known_devices(MAC)),
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk_side_effect,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_coordinator_entry.entry_id)
        await hass.async_block_till_done()
        await _async_advance_poll(hass, freezer)

        # First poll succeeded - entity should be home

        entity_id = entity_registry.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
        )
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

    with (
        patch(
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk,
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
            "homeassistant.components.snmp.client.bulk_walk_cmd",
            side_effect=mock_walk,
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
    freezer: FrozenDateTimeFactory,
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

    with (
        patch_yaml_files(_known_devices(MAC)),
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
        await _async_advance_poll(hass, freezer)

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


async def test_legacy_tracked_dev_ids_skips_unusable_macs(
    hass: HomeAssistant,
) -> None:
    """Test that tracked devices without a usable MAC are left out."""
    devices = [
        Mock(track=True, mac=None, dev_id="no_mac"),
        Mock(track=True, mac="not-a-mac", dev_id="bad_mac"),
        Mock(track=False, mac="00:11:22:33:44:55", dev_id="not_tracked"),
        Mock(track=True, mac="00:11:22:33:44:66", dev_id="tracked"),
    ]

    with patch(
        "homeassistant.components.snmp.device_tracker.async_load_config",
        return_value=devices,
    ):
        dev_ids = await _async_legacy_tracked_dev_ids(hass)

    assert dev_ids == {"00:11:22:33:44:66": "tracked"}
