"""The tests for Cover."""

import pytest

from homeassistant.components import cover
from homeassistant.components.cover import ATTR_SPEED, CoverState, NotValidSpeedError
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_TOGGLE,
)
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers.entity import Entity
from homeassistant.setup import async_setup_component

from .common import MockCover

from tests.common import setup_test_component_platform


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
    ent1, ent2, ent3, ent4, ent5, ent6, _ = mock_cover_entities

    # Test init all covers should be open
    assert is_open(hass, ent1)
    assert is_open(hass, ent2, 50)
    assert is_open(hass, ent3)
    assert is_open(hass, ent4)
    assert is_open(hass, ent5, 50)
    assert is_open(hass, ent6)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    await call_service(hass, SERVICE_TOGGLE, ent5)
    await call_service(hass, SERVICE_TOGGLE, ent6)

    # entities should be either closed or closing,
    # depending on if they report transitional states
    assert is_closed(hass, ent1)
    assert is_closing(hass, ent2, 50)
    assert is_closed(hass, ent3)
    assert is_closed(hass, ent4)
    assert is_closing(hass, ent5, 50)
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

    # entities should be in correct state depending on
    # the SUPPORT_STOP feature and cover position
    assert is_open(hass, ent1)
    assert is_closed(hass, ent2, 0)
    assert is_open(hass, ent3)
    assert is_open(hass, ent4)
    assert is_open(hass, ent5, 15)
    assert is_opening(hass, ent6)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    await call_service(hass, SERVICE_TOGGLE, ent5)
    await call_service(hass, SERVICE_TOGGLE, ent6)

    # entities should be in correct state depending on
    # the SUPPORT_STOP feature and cover position
    assert is_closed(hass, ent1)
    assert is_opening(hass, ent2, 0, closed=True)
    assert is_closed(hass, ent3)
    assert is_closed(hass, ent4)
    assert is_opening(hass, ent5, 15)
    assert is_closing(hass, ent6)

    # Without STOP but still reports opening/closing has a 4th possible toggle state
    set_state(ent6, CoverState.CLOSED)
    await call_service(hass, SERVICE_TOGGLE, ent6)
    assert is_opening(hass, ent6)

    # After the unusual state transition: closing -> fully open, toggle should close
    set_state(ent5, CoverState.OPEN)
    await call_service(hass, SERVICE_TOGGLE, ent5)  # Start closing
    assert is_closing(hass, ent5, 15)
    set_state(
        ent5, CoverState.OPEN
    )  # Unusual state transition from closing -> fully open
    set_cover_position(ent5, 100)
    await call_service(hass, SERVICE_TOGGLE, ent5)  # Should close, not open
    assert is_closing(hass, ent5, 100)


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


def _check_state(
    hass: HomeAssistant,
    ent: Entity,
    *,
    expected_state: str,
    expected_position: int | None,
    expected_is_closed: bool,
) -> bool:
    """Check if the state of a cover is as expected."""
    state = hass.states.get(ent.entity_id)
    correct_state = state.state == expected_state
    correct_is_closed = state.attributes.get("is_closed") == expected_is_closed
    correct_position = state.attributes.get("current_position") == expected_position
    return all([correct_state, correct_is_closed, correct_position])


def is_open(hass: HomeAssistant, ent: Entity, position: int | None = None) -> bool:
    """Return if the cover is open based on the statemachine."""
    return _check_state(
        hass,
        ent,
        expected_state=CoverState.OPEN,
        expected_position=position,
        expected_is_closed=False,
    )


def is_opening(
    hass: HomeAssistant,
    ent: Entity,
    position: int | None = None,
    *,
    closed: bool = False,
) -> bool:
    """Return if the cover is opening based on the statemachine."""
    return _check_state(
        hass,
        ent,
        expected_state=CoverState.OPENING,
        expected_position=position,
        expected_is_closed=closed,
    )


def is_closed(hass: HomeAssistant, ent: Entity, position: int | None = None) -> bool:
    """Return if the cover is closed based on the statemachine."""
    return _check_state(
        hass,
        ent,
        expected_state=CoverState.CLOSED,
        expected_position=position,
        expected_is_closed=True,
    )


def is_closing(hass: HomeAssistant, ent: Entity, position: int | None = None) -> bool:
    """Return if the cover is closing based on the statemachine."""
    return _check_state(
        hass,
        ent,
        expected_state=CoverState.CLOSING,
        expected_position=position,
        expected_is_closed=False,
    )


async def test_services_with_speed(
    hass: HomeAssistant,
    mock_cover_entities: list[MockCover],
) -> None:
    """Test speed validation in cover services."""
    setup_test_component_platform(hass, cover.DOMAIN, mock_cover_entities)

    assert await async_setup_component(
        hass, cover.DOMAIN, {cover.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    # ent1 = cover without tilt and position and no speed support
    # ent2 = cover with position but no speed support
    # ent3 .. ent6 not needed in this test
    # speed_cover = cover with speed support
    ent1, ent2, _, _, _, _, speed_cover = mock_cover_entities

    # Test capability attributes include supported_speeds
    state = hass.states.get(speed_cover.entity_id)
    assert state.attributes["supported_speeds"] == ["slow", "fast", "default"]

    # Test open_cover with valid speed passes speed through and changes state
    speed_cover.last_kwargs = None
    await call_service_with_data(
        hass, SERVICE_OPEN_COVER, speed_cover, {ATTR_SPEED: "fast"}
    )
    assert speed_cover.last_kwargs == {"speed": "fast"}
    assert is_opening(hass, speed_cover, 50)

    # Test close_cover with valid speed passes speed through and changes state
    speed_cover.last_kwargs = None
    await call_service_with_data(
        hass, SERVICE_CLOSE_COVER, speed_cover, {ATTR_SPEED: "slow"}
    )
    assert speed_cover.last_kwargs == {"speed": "slow"}
    assert is_closing(hass, speed_cover, 50)

    # Test set_cover_position with valid speed passes speed through
    speed_cover.last_kwargs = None
    await call_service_with_data(
        hass,
        SERVICE_SET_COVER_POSITION,
        speed_cover,
        {"position": 75, ATTR_SPEED: "default"},
    )
    assert speed_cover.last_kwargs == {"position": 75, "speed": "default"}

    # Test invalid speed raises NotValidSpeedError and does not call entity method
    speed_cover.last_kwargs = None
    with pytest.raises(NotValidSpeedError) as exc:
        await call_service_with_data(
            hass, SERVICE_OPEN_COVER, speed_cover, {ATTR_SPEED: "invalid"}
        )
    assert speed_cover.last_kwargs is None
    assert exc.value.translation_key == "not_valid_speed"

    with pytest.raises(NotValidSpeedError) as exc:
        await call_service_with_data(
            hass, SERVICE_CLOSE_COVER, speed_cover, {ATTR_SPEED: "invalid"}
        )
    assert speed_cover.last_kwargs is None
    assert exc.value.translation_key == "not_valid_speed"

    with pytest.raises(NotValidSpeedError) as exc:
        await call_service_with_data(
            hass,
            SERVICE_SET_COVER_POSITION,
            speed_cover,
            {"position": 50, ATTR_SPEED: "invalid"},
        )
    assert speed_cover.last_kwargs is None
    assert exc.value.translation_key == "not_valid_speed"

    # Test cover without supported_speeds ignores speed and executes normally
    await call_service_with_data(hass, SERVICE_OPEN_COVER, ent1, {ATTR_SPEED: "ignore"})
    assert is_open(hass, ent1)
    assert ent1.last_kwargs == {"speed": "ignore"}

    ent1.last_kwargs = None
    await call_service_with_data(
        hass, SERVICE_CLOSE_COVER, ent1, {ATTR_SPEED: "ignore"}
    )
    assert is_closed(hass, ent1)
    assert ent1.last_kwargs == {"speed": "ignore"}

    ent2.last_kwargs = None
    await call_service_with_data(
        hass, SERVICE_SET_COVER_POSITION, ent2, {"position": 49, ATTR_SPEED: "ignore"}
    )
    assert ent2.last_kwargs == {"position": 49, "speed": "ignore"}


def call_service_with_data(
    hass: HomeAssistant, service: str, ent: Entity, data: dict[str, object]
) -> ServiceResponse:
    """Call any service on entity with data."""
    return hass.services.async_call(
        cover.DOMAIN,
        service,
        {ATTR_ENTITY_ID: ent.entity_id, **data},
        blocking=True,
    )
