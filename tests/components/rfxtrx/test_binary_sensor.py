"""The tests for the Rfxtrx sensor platform."""
from datetime import timedelta

from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import _signal_event

from tests.common import async_fire_time_changed


async def test_one(hass, rfxtrx):
    """Test with 1 sensor."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "devices": {"0b1100cd0213c7f230010f71": {}},
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"


async def test_one_pt2262(hass, rfxtrx):
    """Test with 1 sensor."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "devices": {
                    "0913000022670e013970": {
                        "data_bits": 4,
                        "command_on": 0xE,
                        "command_off": 0x7,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state
    assert state.state == "off"  # probably aught to be unknown
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    await _signal_event(hass, "0913000022670e013970")
    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state.state == "on"

    await _signal_event(hass, "09130000226707013d70")
    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state.state == "off"


async def test_several(hass, rfxtrx):
    """Test with 3."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "devices": {
                    "0b1100cd0213c7f230010f71": {},
                    "0b1100100118cdea02010f70": {},
                    "0b1100101118cdea02010f70": {},
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"

    state = hass.states.get("binary_sensor.ac_1118cdea_2")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 1118cdea:2"


async def test_discover(hass, rfxtrx):
    """Test with discovery."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "automatic_add": True,
                "devices": {
                    "0b1100cd0213c7f230010f71": {},
                    "0b1100100118cdea02010f70": {},
                    "0b1100101118cdea02010f70": {},
                },
            }
        },
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await _signal_event(hass, "0b1100100118cdeb02010f70")
    state = hass.states.get("binary_sensor.ac_118cdeb_2")
    assert state
    assert state.state == "on"


async def test_off_delay(hass, rfxtrx):
    """Test with discovery."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "devices": {"0b1100100118cdea02010f70": {"off_delay": 5}},
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "off"

    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    base_time = utcnow()

    async_fire_time_changed(hass, base_time + timedelta(seconds=4))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "on"

    async_fire_time_changed(hass, base_time + timedelta(seconds=6))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    assert state.state == "off"
