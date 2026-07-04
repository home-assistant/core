"""Tests for the nexia number platform."""

from nexia.home import NexiaHome

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_create_fan_speed_number_entities(
    hass: HomeAssistant, patch_nexia_home: NexiaHome
) -> None:
    """Test creation of fan speed number entities."""

    await setup_integration(hass, patch_nexia_home)

    state = hass.states.get("number.master_suite_fan_speed")
    assert state is not None
    assert state.state == "35.0"
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite Fan speed",
        "min": 35,
        "max": 100,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("number.downstairs_east_wing_fan_speed")
    assert state is not None
    assert state.state == "45.0"
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Downstairs East Wing Fan speed",
        "min": 35,
        "max": 100,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )


async def test_set_fan_speed(hass: HomeAssistant, patch_nexia_home: NexiaHome) -> None:
    """Test setting fan speed."""

    await setup_integration(hass, patch_nexia_home)

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
