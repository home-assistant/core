"""The number entity tests for the nexia platform."""

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_create_fan_speed_number_entities(hass: HomeAssistant) -> None:
    """Test creation of fan speed number entities."""

    await async_init_integration(hass)

    state = hass.states.get("number.master_suite_fan_speed")
    assert state.state == "35.0"
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite Fan Speed",
        "min": 35,
        "max": 100,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )

    state = hass.states.get("number.downstairs_east_wing_fan_speed")
    assert state.state == "35.0"
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Downstairs East Wing Fan Speed",
        "min": 35,
        "max": 100,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == expected_attributes[key] for key in expected_attributes
    )


async def test_set_fan_speed(hass: HomeAssistant) -> None:
    """Test setting fan speed."""

    await async_init_integration(hass)

    state_before = hass.states.get("number.master_suite_fan_speed")
    assert state_before.state == "35.0"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 50},
        blocking=True,
        target={"entity_id": "number.master_suite_fan_speed"},
    )
    state = hass.states.get("number.master_suite_fan_speed")
    assert state.state == "50.0"
