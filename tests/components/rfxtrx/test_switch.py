"""The tests for the RFXtrx switch platform."""
from unittest.mock import call

import pytest

from homeassistant import config_entries
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.rfxtrx.conftest import create_rfx_test_cfg

EVENT_RFY_ENABLE_SUN_AUTO = "0C1a0000030101011300000003"
EVENT_RFY_DISABLE_SUN_AUTO = "0C1a0000030101011400000003"


async def test_one_switch(hass, rfxtrx):
    """Test with 1 switch."""
    entry_data = create_rfx_test_cfg(devices={"0b1100cd0213c7f210010f51": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:16"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.ac_213c7f2_16"}, blocking=True
    )

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state.state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.ac_213c7f2_16"}, blocking=True
    )

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state.state == "off"

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x01\x00\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x00\x00\x00")),
    ]


async def test_one_pt2262_switch(hass, rfxtrx):
    """Test with 1 PT2262 switch."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0913000022670e013970": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            }
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.pt2262_22670e")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.pt2262_22670e"}, blocking=True
    )

    state = hass.states.get("switch.pt2262_22670e")
    assert state.state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.pt2262_22670e"}, blocking=True
    )

    state = hass.states.get("switch.pt2262_22670e")
    assert state.state == "off"

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x09\x13\x00\x00\x22\x67\x0e\x01\x39\x00")),
        call(bytearray(b"\x09\x13\x00\x00\x22\x67\x0f\x01\x39\x00")),
    ]


@pytest.mark.parametrize("state", ["on", "off"])
async def test_state_restore(hass, rfxtrx, state):
    """State restoration."""

    entity_id = "switch.ac_213c7f2_16"

    mock_restore_cache(hass, [State(entity_id, state)])

    entry_data = create_rfx_test_cfg(devices={"0b1100cd0213c7f210010f51": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


async def test_several_switches(hass, rfxtrx):
    """Test with 3 switches."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0b1100cd0213c7f230010f71": {},
            "0b1100100118cdea02010f70": {},
            "0b1100101118cdea02010f70": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.ac_213c7f2_48")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    state = hass.states.get("switch.ac_118cdea_2")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"

    state = hass.states.get("switch.ac_1118cdea_2")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 1118cdea:2"


async def test_switch_events(hass, rfxtrx):
    """Event test with 2 switches."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0b1100cd0213c7f205010f51": {},
            "0b1100cd0213c7f210010f51": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:16"

    state = hass.states.get("switch.ac_213c7f2_5")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:5"

    # "16: On"
    await rfxtrx.signal("0b1100100213c7f210010f70")
    assert hass.states.get("switch.ac_213c7f2_5").state == STATE_UNKNOWN
    assert hass.states.get("switch.ac_213c7f2_16").state == "on"

    # "16: Off"
    await rfxtrx.signal("0b1100100213c7f210000f70")
    assert hass.states.get("switch.ac_213c7f2_5").state == STATE_UNKNOWN
    assert hass.states.get("switch.ac_213c7f2_16").state == "off"

    # "5: On"
    await rfxtrx.signal("0b1100100213c7f205010f70")
    assert hass.states.get("switch.ac_213c7f2_5").state == "on"
    assert hass.states.get("switch.ac_213c7f2_16").state == "off"

    # "5: Off"
    await rfxtrx.signal("0b1100100213c7f205000f70")
    assert hass.states.get("switch.ac_213c7f2_5").state == "off"
    assert hass.states.get("switch.ac_213c7f2_16").state == "off"

    # "16: Group on"
    await rfxtrx.signal("0b1100100213c7f210040f70")
    assert hass.states.get("switch.ac_213c7f2_5").state == "on"
    assert hass.states.get("switch.ac_213c7f2_16").state == "on"

    # "16: Group off"
    await rfxtrx.signal("0b1100100213c7f210030f70")
    assert hass.states.get("switch.ac_213c7f2_5").state == "off"
    assert hass.states.get("switch.ac_213c7f2_16").state == "off"


async def test_pt2262_switch_events(hass, rfxtrx):
    """Test with 1 PT2262 switch."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0913000022670e013970": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            }
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.pt2262_22670e")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    # "Command: 0xE"
    await rfxtrx.signal("0913000022670e013970")
    assert hass.states.get("switch.pt2262_22670e").state == "on"

    # "Command: 0x0"
    await rfxtrx.signal("09130000226700013970")
    assert hass.states.get("switch.pt2262_22670e").state == "on"

    # "Command: 0x7"
    await rfxtrx.signal("09130000226707013d70")
    assert hass.states.get("switch.pt2262_22670e").state == "off"

    # "Command: 0x1"
    await rfxtrx.signal("09130000226701013d70")
    assert hass.states.get("switch.pt2262_22670e").state == "off"


async def test_discover_switch(hass, rfxtrx_automatic):
    """Test with discovery of switches."""
    rfxtrx = rfxtrx_automatic

    await rfxtrx.signal("0b1100100118cdea02010f70")
    state = hass.states.get("switch.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await rfxtrx.signal("0b1100100118cdeb02010f70")
    state = hass.states.get("switch.ac_118cdeb_2")
    assert state
    assert state.state == "on"


async def test_discover_rfy_sun_switch(hass, rfxtrx_automatic):
    """Test with discovery of switches."""
    rfxtrx = rfxtrx_automatic

    await rfxtrx.signal(EVENT_RFY_DISABLE_SUN_AUTO)
    state = hass.states.get("switch.rfy_030101_1")
    assert state
    assert state.state == "off"

    await rfxtrx.signal(EVENT_RFY_ENABLE_SUN_AUTO)
    state = hass.states.get("switch.rfy_030101_1")
    assert state
    assert state.state == "on"


async def test_unknown_event_code(hass, rfxtrx):
    """Test with 3 switches."""
    entry_data = create_rfx_test_cfg(devices={"1234567890": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(conf_entries) == 1

    entry = conf_entries[0]
    assert entry.state == config_entries.ConfigEntryState.LOADED
