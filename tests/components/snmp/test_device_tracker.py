"""Tests for the SNMP device tracker."""

import binascii
from datetime import timedelta
from unittest.mock import Mock, patch

from pysnmp.proto.rfc1902 import OctetString
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import CONF_IMPORTED_BY, DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

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


async def test_device_tracker_setup_with_legacy_state(
    hass: HomeAssistant, mock_walk, mock_get_cmd
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
            CONF_IMPORTED_BY: "device_tracker",
        },
    )
    entry.add_to_hass(hass)

    # Simulate a legacy tracked device with existing state
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    with patch(
        "homeassistant.components.snmp.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )

    assert entity_id is not None

    # Entity should be enabled because it was migrated from a legacy state
    ent_entry = ent_reg.async_get(entity_id)
    assert ent_entry is not None
    assert ent_entry.disabled_by is None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "00:11:22:33:44:55"
    assert state.attributes["ip"] == "192.168.1.1"


async def test_device_tracker_new_entity_disabled_by_default(
    hass: HomeAssistant, mock_walk, mock_get_cmd
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

    with patch(
        "homeassistant.components.snmp.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )

    assert entity_id is not None

    # Entity should be disabled by default (no legacy state, no device)
    ent_entry = ent_reg.async_get(entity_id)
    assert ent_entry is not None
    assert ent_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # No state should be present since the entity is disabled
    assert hass.states.get(entity_id) is None


async def test_device_tracker_update(
    hass: HomeAssistant, mock_walk, mock_get_cmd
) -> None:
    """Test update of SNMP device tracker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
            CONF_IMPORTED_BY: "device_tracker",
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

    with patch(
        "homeassistant.components.snmp.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id_1 = ent_reg.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac1_str)
    assert entity_id_1 is not None
    assert hass.states.get(entity_id_1).state == STATE_HOME
    assert hass.states.get(entity_id_1).attributes["ip"] == "192.168.1.1"

    mock_walk.side_effect = mock_walk_2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    # mac2 is a newly discovered device (no legacy state) → disabled
    entity_id_2 = ent_reg.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac2_str)
    assert entity_id_2 is not None

    entry2 = ent_reg.async_get(entity_id_2)
    assert entry2 is not None
    assert entry2.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    # mac1 should now be not_home since it's no longer in the walk results
    assert hass.states.get(entity_id_1).state == STATE_NOT_HOME
    # mac2 is disabled so no state
    assert hass.states.get(entity_id_2) is None


async def test_device_tracker_device_registry_linking(
    hass: HomeAssistant, mock_walk, mock_get_cmd
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

    dr_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    mac = "00:11:22:33:44:55"

    with patch(
        "homeassistant.components.snmp.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify Host Device
    host_device = dr_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert host_device is not None

    # Verify Client Device Linking (it should not exist because device_info was removed)
    client_device = dr_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert client_device is None

    # Verify Entity Linking
    entity_id = ent_reg.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac)
    reg_entry = ent_reg.async_get(entity_id)
    assert reg_entry is not None
    assert reg_entry.device_id is None
    assert reg_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_device_tracker_name_resolves_to_mac_address(
    hass: HomeAssistant, mock_walk, mock_get_cmd
) -> None:
    """Test that the entity name resolves to the expected MAC address format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.4.22.1.6",
            "community": "public",
            CONF_IMPORTED_BY: "device_tracker",
        },
    )
    entry.add_to_hass(hass)

    # Enable entity by setting legacy state
    hass.states.async_set("device_tracker.00_11_22_33_44_55", STATE_HOME)

    with patch(
        "homeassistant.components.snmp.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "00_11_22_33_44_55"
