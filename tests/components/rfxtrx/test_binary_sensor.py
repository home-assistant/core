"""The tests for the Rfxtrx sensor platform."""
from datetime import timedelta

from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import _signal_event

from tests.common import async_fire_time_changed


async def test_default_config(hass, rfxtrx):
    """Test with 0 sensor."""
    await async_setup_component(
        hass, "binary_sensor", {"binary_sensor": {"platform": "rfxtrx", "devices": {}}}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_one(hass, rfxtrx):
    """Test with 1 sensor."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "rfxtrx",
                "devices": {"0a52080705020095220269": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"


async def test_one_pt2262(hass, rfxtrx):
    """Test with 1 sensor."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "rfxtrx",
                "devices": {
                    "0913000022670e013970": {
                        "name": "Test",
                        "data_bits": 4,
                        "command_on": 0xE,
                        "command_off": 0x7,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "off"  # probably aught to be unknown
    assert state.attributes.get("friendly_name") == "Test"

    await _signal_event(hass, "0913000022670e013970")
    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "Test"

    await _signal_event(hass, "09130000226707013d70")
    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"


async def test_several(hass, rfxtrx):
    """Test with 3."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "rfxtrx",
                "devices": {
                    "0b1100cd0213c7f230010f71": {"name": "Test"},
                    "0b1100100118cdea02010f70": {"name": "Bath"},
                    "0b1100101118cdea02010f70": {"name": "Living"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"

    state = hass.states.get("binary_sensor.bath")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Bath"

    state = hass.states.get("binary_sensor.living")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Living"


async def test_discover(hass, rfxtrx):
    """Test with discovery."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {"binary_sensor": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.0b1100100118cdea02010f70")
    assert state
    assert state.state == "on"

    await _signal_event(hass, "0b1100100118cdeb02010f70")
    state = hass.states.get("binary_sensor.0b1100100118cdeb02010f70")
    assert state
    assert state.state == "on"

    # Trying to add a sensor
    await _signal_event(hass, "0a52085e070100b31b0279")
    state = hass.states.get("sensor.0a52085e070100b31b0279")
    assert state is None

    # Trying to add a light
    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("light.0b1100100118cdea02010f70")
    assert state is None

    # Trying to add a rollershutter
    await _signal_event(hass, "0a1400adf394ab020e0060")
    state = hass.states.get("cover.0a1400adf394ab020e0060")
    assert state is None


async def test_discover_noautoadd(hass, rfxtrx):
    """Test with discovery of switch when auto add is False."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "rfxtrx",
                "automatic_add": False,
                "devices": {},
            }
        },
    )
    await hass.async_block_till_done()

    # Trying to add switch
    await _signal_event(hass, "0b1100100118cdea02010f70")
    assert hass.states.async_all() == []


async def test_off_delay(hass, rfxtrx):
    """Test with discovery."""
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "rfxtrx",
                "automatic_add": True,
                "devices": {
                    "0b1100100118cdea02010f70": {"name": "Test", "off_delay": 5}
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "off"

    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "on"

    base_time = utcnow()

    async_fire_time_changed(hass, base_time + timedelta(seconds=4))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "on"

    async_fire_time_changed(hass, base_time + timedelta(seconds=6))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state
    assert state.state == "off"
