"""Tests for the Solyx Energy sensor platform."""

from typing import TYPE_CHECKING

import pytest

from homeassistant.components.solyx_energy.const import DOMAIN

from .const import NYMO_DEVICE_ID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import EntityRegistry


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("powerBoiler", ("1234.0", "W", "power")),
        ("energyBoiler", ("5678.0", "Wh", "energy")),
        ("gridPower", ("-100.0", "W", "power")),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    init_integration,
    key,
    expected,
) -> None:
    """Test each sensor has the correct state, unit, and device class."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{NYMO_DEVICE_ID}-{key}"
    )
    assert entity_id is not None

    # Check the state, unit, and device class match the API data.
    state = hass.states.get(entity_id)
    assert state is not None
    value, unit, device_class = expected
    assert state.state == value
    assert state.attributes["unit_of_measurement"] == unit
    assert state.attributes["device_class"] == device_class
