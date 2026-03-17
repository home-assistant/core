"""Tests for the SNMP device tracker."""

import binascii
from datetime import timedelta
from unittest.mock import Mock, patch

from pysnmp.proto.rfc1902 import OctetString
import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.snmp.const import DOMAIN
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
        yield None, None, None, [("oid1", OctetString(mac1))]

    with patch(
        "homeassistant.components.snmp.coordinator.bulk_walk_cmd",
        side_effect=side_effect,
    ) as mock:
        yield mock


async def test_device_tracker_setup(hass: HomeAssistant, mock_walk) -> None:
    """Test setup of SNMP device tracker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.3.1.1.2",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    dr_reg = dr.async_get(hass)
    dr_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:55")},
    )

    with patch(
        "homeassistant.components.snmp.device_tracker.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        DEVICE_TRACKER_DOMAIN, DOMAIN, "00:11:22:33:44:55"
    )
    if entity_id is None:
        entity_id = ent_reg.async_get_entity_id(
            DEVICE_TRACKER_DOMAIN, DOMAIN, "001122334455"
        )

    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "00:11:22:33:44:55"


async def test_device_tracker_update(hass: HomeAssistant, mock_walk) -> None:
    """Test update of SNMP device tracker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.2.1.3.1.1.2",
            "community": "public",
        },
    )
    entry.add_to_hass(hass)

    mac1 = binascii.unhexlify("001122334455")
    mac2 = binascii.unhexlify("aabbccddeeff")
    mac1_str = "00:11:22:33:44:55"
    mac2_str = "aa:bb:cc:dd:ee:ff"

    dr_reg = dr.async_get(hass)
    for m_str in (mac1_str, mac2_str):
        dr_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, m_str)},
        )

    async def mock_walk_1(*args, **kwargs):
        yield None, None, None, [("oid1", OctetString(mac1))]

    async def mock_walk_2(*args, **kwargs):
        yield None, None, None, [("oid2", OctetString(mac2))]

    mock_walk.side_effect = mock_walk_1

    with patch(
        "homeassistant.components.snmp.device_tracker.UdpTransportTarget.create",
        return_value=Mock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id_1 = ent_reg.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac1_str)
    assert entity_id_1 is not None
    assert hass.states.get(entity_id_1).state == STATE_HOME

    mock_walk.side_effect = mock_walk_2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    entity_id_2 = ent_reg.async_get_entity_id(DEVICE_TRACKER_DOMAIN, DOMAIN, mac2_str)
    assert entity_id_2 is not None

    assert hass.states.get(entity_id_1).state == STATE_NOT_HOME
    assert hass.states.get(entity_id_2).state == STATE_HOME
