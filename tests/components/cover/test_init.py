"""The tests for Cover."""

from enum import Enum

from homeassistant.components import cover
from homeassistant.components.cover import CoverState
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, SERVICE_TOGGLE
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers.entity import Entity
from homeassistant.setup import async_setup_component

from .common import MockCover

from tests.common import help_test_all, setup_test_component_platform


async def test_services(
    hass: HomeAssistant,
    mock_cover_entities: list[MockCover],
) -> None:
    """Test the provided services."""
    setup_test_component_platform(hass, cover.DOMAIN, mock_cover_entities)

    assert await async_setup_component(
        hass, cover.DOMAIN, {cover.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    # ent1 = cover without tilt and position
    # ent2 = cover with position but no tilt
    # ent3 = cover with simple tilt functions and no position
    # ent4 = cover with all tilt functions but no position
    # ent5 = cover with all functions
    # ent6 = cover with only open/close, but also reports opening/closing
    ent1, ent2, ent3, ent4, ent5, ent6 = mock_cover_entities

    # Test init all covers should be open
    assert is_open(hass, ent1)
    assert is_open(hass, ent2)
    assert is_open(hass, ent3)
    assert is_open(hass, ent4)
    assert is_open(hass, ent5)
    assert is_open(hass, ent6)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    await call_service(hass, SERVICE_TOGGLE, ent5)
    await call_service(hass, SERVICE_TOGGLE, ent6)

    # entities should be either closed or closing, depending on if they report transitional states
    assert is_closed(hass, ent1)
    assert is_closing(hass, ent2)
    assert is_closed(hass, ent3)
    assert is_closed(hass, ent4)
    assert is_closing(hass, ent5)
    assert is_closing(hass, ent6)

    # call basic toggle services and set different cover position states
    await call_service(hass, SERVICE_TOGGLE, ent1)
    set_cover_position(ent2, 0)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    set_cover_position(ent5, 15)
    await call_service(hass, SERVICE_TOGGLE, ent5)
    await call_service(hass, SERVICE_TOGGLE, ent6)

    # entities should be in correct state depending on the SUPPORT_STOP feature and cover position
    assert is_open(hass, ent1)
    assert is_closed(hass, ent2)
    assert is_open(hass, ent3)
    assert is_open(hass, ent4)
    assert is_open(hass, ent5)
    assert is_opening(hass, ent6)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    await call_service(hass, SERVICE_TOGGLE, ent5)
    await call_service(hass, SERVICE_TOGGLE, ent6)

    # entities should be in correct state depending on the SUPPORT_STOP feature and cover position
    assert is_closed(hass, ent1)
    assert is_opening(hass, ent2)
    assert is_closed(hass, ent3)
    assert is_closed(hass, ent4)
    assert is_opening(hass, ent5)
    assert is_closing(hass, ent6)

    # Without STOP but still reports opening/closing has a 4th possible toggle state
    set_state(ent6, CoverState.CLOSED)
    await call_service(hass, SERVICE_TOGGLE, ent6)
    assert is_opening(hass, ent6)

    # After the unusual state transition: closing -> fully open, toggle should close
    set_state(ent5, CoverState.OPEN)
    await call_service(hass, SERVICE_TOGGLE, ent5)  # Start closing
    assert is_closing(hass, ent5)
    set_state(
        ent5, CoverState.OPEN
    )  # Unusual state transition from closing -> fully open
    set_cover_position(ent5, 100)
    await call_service(hass, SERVICE_TOGGLE, ent5)  # Should close, not open
    assert is_closing(hass, ent5)


def call_service(hass: HomeAssistant, service: str, ent: Entity) -> ServiceResponse:
    """Call any service on entity."""
    return hass.services.async_call(
        cover.DOMAIN, service, {ATTR_ENTITY_ID: ent.entity_id}, blocking=True
    )


def set_cover_position(ent, position) -> None:
    """Set a position value to a cover."""
    ent._values["current_cover_position"] = position


def set_state(ent, state) -> None:
    """Set the state of a cover."""
    ent._values["state"] = state


def is_open(hass: HomeAssistant, ent: Entity) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, CoverState.OPEN)


def is_opening(hass: HomeAssistant, ent: Entity) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, CoverState.OPENING)


def is_closed(hass: HomeAssistant, ent: Entity) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, CoverState.CLOSED)


def is_closing(hass: HomeAssistant, ent: Entity) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, CoverState.CLOSING)


def _create_tuples(enum: type[Enum], constant_prefix: str) -> list[tuple[Enum, str]]:
    return [(enum_field, constant_prefix) for enum_field in enum]


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(cover)
