"""The tests for Octoptint binary sensor module."""

from homeassistant.const import STATE_OFF, STATE_ON

from . import init_integration


async def test_sensors(hass):
    """Test the underlying sensors."""
    printer = {
        "state": {
            "flags": {"printing": True, "error": False},
            "text": "Operational",
        },
        "temperature": [],
    }
    await init_integration(hass, "binary_sensor", printer=printer)

    state = hass.states.get("binary_sensor.octoprint_printing")
    assert state is not None
    assert state.state == STATE_ON
    assert state.name == "Octoprint Printing"

    state = hass.states.get("binary_sensor.octoprint_printing_error")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.name == "Octoprint Printing Error"
