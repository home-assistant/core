"""The tests for Valve."""
import homeassistant.components.valve as valve
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TOGGLE,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_services(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test the provided services."""
    platform = getattr(hass.components, "test.valve")

    platform.init()
    assert await async_setup_component(
        hass, valve.DOMAIN, {valve.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    # ent1 = valve without position
    # ent2 = valve with position
    ent1, ent2 = platform.ENTITIES

    # Test init all valves should be open
    assert is_open(hass, ent1)
    assert is_open(hass, ent2)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities without stop should be closed and with stop should be closing
    assert is_closed(hass, ent1)
    assert is_closing(hass, ent2)

    # call basic toggle services and set different valve position states
    await call_service(hass, SERVICE_TOGGLE, ent1)
    set_valve_position(ent2, 0)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities should be in correct state depending on the SUPPORT_STOP feature and valve position
    assert is_open(hass, ent1)
    assert is_closed(hass, ent2)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities should be in correct state depending on the SUPPORT_STOP feature and valve position
    assert is_closed(hass, ent1)
    assert is_opening(hass, ent2)


def call_service(hass, service, ent):
    """Call any service on entity."""
    return hass.services.async_call(
        valve.DOMAIN, service, {ATTR_ENTITY_ID: ent.entity_id}, blocking=True
    )


def set_valve_position(ent, position) -> None:
    """Set a position value to a valve."""
    ent._values["current_valve_position"] = position


def is_open(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_OPEN)


def is_opening(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_OPENING)


def is_closed(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return valve.is_closed(hass, ent.entity_id)


def is_closing(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_CLOSING)
