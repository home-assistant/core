"""The tests for Cover."""

from typing import Any

import pytest
from pytest_homeassistant.common import (
    async_capture_events,
    setup_test_component_platform,
)

from homeassistant.components import cover
from homeassistant.components.cover import ATTR_SPEED, CoverEntityFeature, CoverState
from homeassistant.components.cover.const import ATTR_POSITION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
)
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.setup import async_setup_component

from .common import MockCover


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


async def test_toggle_after_opened_outside_home_assistant(
    hass: HomeAssistant,
    mock_cover_entities: list[MockCover],
) -> None:
    """Test toggle closes a cover that opened without reporting opening."""
    setup_test_component_platform(hass, cover.DOMAIN, mock_cover_entities)

    assert await async_setup_component(
        hass, cover.DOMAIN, {cover.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    # ent6 = cover with only open/close, but also reports opening/closing,
    # like a garage door opener with a contact sensor
    ent6 = mock_cover_entities[5]

    # Closed by Home Assistant: it reports closing, then closed
    await call_service(hass, SERVICE_TOGGLE, ent6)
    assert is_closing(hass, ent6)
    set_state(ent6, CoverState.CLOSED)
    ent6.async_write_ha_state()
    assert is_closed(hass, ent6)

    # Opened outside Home Assistant (a wall button or remote): straight to open
    set_state(ent6, CoverState.OPEN)
    ent6.async_write_ha_state()
    assert is_open(hass, ent6)

    # Toggle should close it, not send open to an open cover
    await call_service(hass, SERVICE_TOGGLE, ent6)
    assert is_closing(hass, ent6)


TILT_FEATURES = (
    CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)


def _tilt_cover(**values: Any) -> MockCover:
    """Return a cover that can set its tilt position."""
    return MockCover(
        name="Cover", unique_id="cover", supported_features=TILT_FEATURES, **values
    )


def _tilt_attributes(hass: HomeAssistant, ent: MockCover) -> dict[str, Any]:
    """Return the tilt capability attributes of the state of a cover."""
    attributes = hass.states.get(ent.entity_id).attributes
    return {
        key: attributes[key]
        for key in (
            "open_tilt_position",
            "closed_tilt_positions",
            "tilt_start_angle",
            "tilt_end_angle",
        )
        if key in attributes
    }


async def _setup_cover(hass: HomeAssistant, ent: MockCover) -> None:
    """Set up a cover entity."""
    setup_test_component_platform(hass, cover.DOMAIN, [ent])
    assert await async_setup_component(
        hass, cover.DOMAIN, {cover.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()


def _angles(start: int, end: int) -> dict[str, int]:
    """Return the tilt angles of a cover."""
    return {"tilt_start_angle": start, "tilt_end_angle": end}


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        pytest.param(
            {},
            {"open_tilt_position": 100, "closed_tilt_positions": [0]},
            id="default",
        ),
        pytest.param(
            {"open_tilt_position": 50},
            {"open_tilt_position": 50, "closed_tilt_positions": [0]},
            id="open_position_set",
        ),
        pytest.param(
            {"open_tilt_position": 0},
            {"open_tilt_position": 0, "closed_tilt_positions": [100]},
            id="open_at_0",
        ),
        pytest.param(
            {"open_tilt_position": 50, "closed_tilt_positions": [100, 0]},
            {"open_tilt_position": 50, "closed_tilt_positions": [0, 100]},
            id="closed_positions_set",
        ),
        pytest.param(
            {"open_tilt_position": 50, "closed_tilt_positions": [10, 100]},
            {"open_tilt_position": 50, "closed_tilt_positions": [100]},
            id="closed_position_inside_the_scale_is_dropped",
        ),
        pytest.param(
            {"closed_tilt_positions": [0, 100]},
            {"open_tilt_position": 100, "closed_tilt_positions": [0]},
            id="closed_positions_with_the_open_position",
        ),
        pytest.param(
            {"closed_tilt_positions": []},
            {"open_tilt_position": 100, "closed_tilt_positions": [0]},
            id="closed_positions_empty",
        ),
        pytest.param(
            {"closed_tilt_positions": [10]},
            {"open_tilt_position": 100, "closed_tilt_positions": [0]},
            id="only_closed_position_inside_the_scale",
        ),
        pytest.param(
            _angles(-90, 90),
            {"open_tilt_position": 50, "closed_tilt_positions": [0, 100]}
            | _angles(-90, 90),
            id="180_degrees",
        ),
        pytest.param(
            _angles(-90, 0),
            {"open_tilt_position": 100, "closed_tilt_positions": [0]} | _angles(-90, 0),
            id="90_degrees",
        ),
        pytest.param(
            _angles(-90, 60),
            {"open_tilt_position": 60, "closed_tilt_positions": [0]} | _angles(-90, 60),
            id="pergola",
        ),
        pytest.param(
            _angles(-90, 45),
            {"open_tilt_position": 67, "closed_tilt_positions": [0]} | _angles(-90, 45),
            id="rounded_open_position",
        ),
        pytest.param(
            _angles(-60, 60),
            {"open_tilt_position": 50, "closed_tilt_positions": [0, 100]}
            | _angles(-60, 60),
            id="slats_never_flat",
        ),
        pytest.param(
            _angles(-45, 90),
            {"open_tilt_position": 33, "closed_tilt_positions": [100]}
            | _angles(-45, 90),
            id="range_not_symmetric",
        ),
        pytest.param(
            _angles(30, 90),
            {"open_tilt_position": 0, "closed_tilt_positions": [100]} | _angles(30, 90),
            id="never_perpendicular_open_at_0",
        ),
        pytest.param(
            _angles(-90, -30),
            {"open_tilt_position": 100, "closed_tilt_positions": [0]}
            | _angles(-90, -30),
            id="never_perpendicular_open_at_100",
        ),
        pytest.param(
            _angles(0, 60),
            {"open_tilt_position": 0, "closed_tilt_positions": [100]} | _angles(0, 60),
            id="open_at_0_never_flat",
        ),
        pytest.param(
            _angles(0, -80),
            {"open_tilt_position": 0, "closed_tilt_positions": [100]} | _angles(0, -80),
            id="angle_goes_down",
        ),
        pytest.param(
            _angles(-90, 45) | {"open_tilt_position": 100},
            {"open_tilt_position": 100, "closed_tilt_positions": [0]}
            | _angles(-90, 45),
            id="open_position_overrides_angles",
        ),
        pytest.param(
            _angles(-90, 90) | {"closed_tilt_positions": [0]},
            {"open_tilt_position": 50, "closed_tilt_positions": [0]} | _angles(-90, 90),
            id="closed_positions_override_angles",
        ),
        pytest.param(
            {"tilt_start_angle": -90},
            {"open_tilt_position": 100, "closed_tilt_positions": [0]},
            id="one_angle",
        ),
        pytest.param(
            _angles(90, 90),
            {"open_tilt_position": 100, "closed_tilt_positions": [0]},
            id="equal_angles",
        ),
    ],
)
async def test_tilt_capability_attributes(
    hass: HomeAssistant, values: dict[str, Any], expected: dict[str, Any]
) -> None:
    """Test the tilt capability attributes."""
    ent = _tilt_cover(**values)
    await _setup_cover(hass, ent)

    assert _tilt_attributes(hass, ent) == expected


@pytest.mark.parametrize(
    "supported_features",
    [
        pytest.param(CoverEntityFeature.OPEN, id="no_tilt"),
        pytest.param(
            CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT,
            id="open_and_close_tilt_only",
        ),
    ],
)
async def test_no_tilt_capability_attributes_without_tilt_position(
    hass: HomeAssistant, supported_features: CoverEntityFeature
) -> None:
    """Test a cover that cannot set its tilt position has no tilt attributes."""
    ent = MockCover(
        name="Cover",
        unique_id="cover",
        supported_features=supported_features,
        open_tilt_position=50,
        **_angles(-90, 90),
    )
    await _setup_cover(hass, ent)

    assert _tilt_attributes(hass, ent) == {}


async def test_tilt_capability_attributes_change(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the state and the registry follow the tilt values of the cover."""
    ent = _tilt_cover()
    await _setup_cover(hass, ent)
    default = {"open_tilt_position": 100, "closed_tilt_positions": [0]}
    assert _tilt_attributes(hass, ent) == default
    assert entity_registry.async_get(ent.entity_id).capabilities == default

    ent._values.update(_angles(-90, 90))
    ent.async_write_ha_state()
    await hass.async_block_till_done()

    changed = {"open_tilt_position": 50, "closed_tilt_positions": [0, 100]} | _angles(
        -90, 90
    )
    assert _tilt_attributes(hass, ent) == changed
    assert entity_registry.async_get(ent.entity_id).capabilities == changed


async def test_tilt_capability_attributes_unchanged(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test writing the same tilt values again does not update the registry."""
    ent = _tilt_cover(closed_tilt_positions=(100, 0), open_tilt_position=50)
    await _setup_cover(hass, ent)
    updates = async_capture_events(hass, er.EVENT_ENTITY_REGISTRY_UPDATED)

    ent.async_write_ha_state()
    await hass.async_block_till_done()

    assert not updates


@pytest.mark.parametrize(
    ("values", "expected_service"),
    [
        pytest.param({"current_cover_tilt_position": 0}, "open", id="closed_at_0"),
        pytest.param({"current_cover_tilt_position": 100}, "close", id="open_at_100"),
        pytest.param({"current_cover_tilt_position": 30}, "close", id="partly_open"),
        pytest.param({"current_cover_tilt_position": None}, "close", id="unknown"),
        pytest.param(
            {"current_cover_tilt_position": 100, "open_tilt_position": 50},
            "close",
            id="100_not_declared_closed",
        ),
        pytest.param(
            {
                "current_cover_tilt_position": 100,
                "open_tilt_position": 50,
                "closed_tilt_positions": [0, 100],
            },
            "open",
            id="closed_at_100",
        ),
        pytest.param(
            {
                "current_cover_tilt_position": 99,
                "open_tilt_position": 50,
                "closed_tilt_positions": [0, 100],
            },
            "close",
            id="almost_closed",
        ),
        pytest.param(
            {"current_cover_tilt_position": 50, "open_tilt_position": 50},
            "close",
            id="open_at_50",
        ),
        pytest.param(
            {"current_cover_tilt_position": 10, "closed_tilt_positions": [10]},
            "close",
            id="closed_inside_the_scale_is_ignored",
        ),
        pytest.param(
            {"current_cover_tilt_position": 100} | _angles(-90, 90),
            "open",
            id="closed_at_100_from_angles",
        ),
        pytest.param(
            {"current_cover_tilt_position": 0} | _angles(-75, 75),
            "open",
            id="closed_at_0_with_slats_never_flat",
        ),
        pytest.param(
            {"current_cover_tilt_position": 100} | _angles(-90, 60),
            "close",
            id="pergola_past_open",
        ),
    ],
)
async def test_toggle_tilt(
    hass: HomeAssistant, values: dict[str, Any], expected_service: str
) -> None:
    """Test toggle tilt opens the slats only at a closed position."""
    ent = _tilt_cover(**values)
    await _setup_cover(hass, ent)

    await call_service(hass, SERVICE_TOGGLE_COVER_TILT, ent)
    assert ent.last_tilt_service == expected_service


async def test_toggle_tilt_without_tilt_position(hass: HomeAssistant) -> None:
    """Test toggle tilt opens at 0 for a cover that cannot set its tilt position."""
    ent = MockCover(
        name="Cover",
        unique_id="cover",
        supported_features=CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT,
        current_cover_tilt_position=0,
    )
    await _setup_cover(hass, ent)

    await call_service(hass, SERVICE_TOGGLE_COVER_TILT, ent)
    assert ent.last_tilt_service == "open"


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
    """Test the speed argument in cover services."""
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

    state = hass.states.get(speed_cover.entity_id)
    assert state.attributes["supported_speeds"] == ["slow", "medium", "fast"]

    speed_cover.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: speed_cover.entity_id, ATTR_SPEED: "fast"},
        blocking=True,
    )
    assert speed_cover.last_kwargs == {"speed": "fast"}
    assert is_opening(hass, speed_cover, 50)

    speed_cover.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: speed_cover.entity_id, ATTR_SPEED: "slow"},
        blocking=True,
    )
    assert speed_cover.last_kwargs == {"speed": "slow"}
    assert is_closing(hass, speed_cover, 50)

    speed_cover.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {
            ATTR_ENTITY_ID: speed_cover.entity_id,
            ATTR_POSITION: 75,
            ATTR_SPEED: "medium",
        },
        blocking=True,
    )
    assert speed_cover.last_kwargs == {"position": 75, "speed": "medium"}

    # A speed the cover does not list is dropped and the cover still moves
    speed_cover.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: speed_cover.entity_id, ATTR_SPEED: "default"},
        blocking=True,
    )
    assert speed_cover.last_kwargs == {}
    assert is_opening(hass, speed_cover, 50)

    speed_cover.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: speed_cover.entity_id, ATTR_SPEED: "invalid"},
        blocking=True,
    )
    assert speed_cover.last_kwargs == {}
    assert is_closing(hass, speed_cover, 50)

    speed_cover.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {
            ATTR_ENTITY_ID: speed_cover.entity_id,
            ATTR_POSITION: 50,
            ATTR_SPEED: "invalid",
        },
        blocking=True,
    )
    assert speed_cover.last_kwargs == {"position": 50}

    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ent1.entity_id, ATTR_SPEED: "ignore"},
        blocking=True,
    )
    assert is_open(hass, ent1)
    assert ent1.last_kwargs == {}

    ent1.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ent1.entity_id, ATTR_SPEED: "ignore"},
        blocking=True,
    )
    assert is_closed(hass, ent1)
    assert ent1.last_kwargs == {}

    ent2.last_kwargs = None
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ent2.entity_id, ATTR_POSITION: 49, ATTR_SPEED: "ignore"},
        blocking=True,
    )
    assert ent2.last_kwargs == {"position": 49}


async def test_deprecated_is_closed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the deprecated is_closed helper."""
    hass.states.async_set("cover.test", CoverState.CLOSED)
    assert cover.is_closed(hass, "cover.test") is True

    hass.states.async_set("cover.test", CoverState.OPEN)
    assert cover.is_closed(hass, "cover.test") is False

    assert (
        "The deprecated function is_closed was called. It will be removed in HA Core "
        "2027.10. Use hass.states.is_state(entity_id, 'closed') instead"
    ) in caplog.text
