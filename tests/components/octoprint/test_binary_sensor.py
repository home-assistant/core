"""The tests for Octoptint binary sensor module."""

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_sensors(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
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
    assert state.name == "OctoPrint Printing"
    entry = entity_registry.async_get("binary_sensor.octoprint_printing")
    assert entry.unique_id == "Printing-uuid"

    state = hass.states.get("binary_sensor.octoprint_printing_error")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.name == "OctoPrint Printing Error"
    entry = entity_registry.async_get("binary_sensor.octoprint_printing_error")
    assert entry.unique_id == "Printing Error-uuid"


async def test_sensors_printer_offline(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the underlying sensors when the printer is offline."""
    await init_integration(hass, "binary_sensor", printer=None)

    state = hass.states.get("binary_sensor.octoprint_printing")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.name == "OctoPrint Printing"
    entry = entity_registry.async_get("binary_sensor.octoprint_printing")
    assert entry.unique_id == "Printing-uuid"

    state = hass.states.get("binary_sensor.octoprint_printing_error")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.name == "OctoPrint Printing Error"
    entry = entity_registry.async_get("binary_sensor.octoprint_printing_error")
    assert entry.unique_id == "Printing Error-uuid"
