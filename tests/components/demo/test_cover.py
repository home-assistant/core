"""The tests for the Demo cover platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import assert_setup_component, async_fire_time_changed

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntityCapabilityAttribute,
    CoverService,
    CoverServiceArgument,
    CoverState,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

CONFIG = {"cover": {"platform": "demo"}}
ENTITY_COVER = "cover.living_room_window"


@pytest.fixture
def cover_only() -> Generator[None]:
    """Enable only the cover platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.COVER],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, cover_only: None) -> None:
    """Set up demo cover component."""
    with assert_setup_component(1, COVER_DOMAIN):
        await async_setup_component(hass, COVER_DOMAIN, CONFIG)
        await hass.async_block_till_done()


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test cover supported features."""
    state = hass.states.get("cover.garage_door")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 3
    state = hass.states.get("cover.kitchen_window")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 11
    state = hass.states.get("cover.hall_window")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 15
    state = hass.states.get("cover.living_room_window")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 511


@pytest.mark.parametrize(
    ("entity_id", "device_class"),
    [
        ("cover.kitchen_window", None),
        ("cover.hall_window", CoverDeviceClass.SHUTTER),
        ("cover.living_room_window", CoverDeviceClass.BLIND),
        ("cover.garage_door", CoverDeviceClass.GARAGE),
        ("cover.pergola_roof", CoverDeviceClass.AWNING),
        ("cover.bedroom_curtains", CoverDeviceClass.CURTAIN),
        ("cover.front_gate", CoverDeviceClass.GATE),
        ("cover.office_blind", CoverDeviceClass.BLIND),
    ],
)
async def test_device_class(
    hass: HomeAssistant, entity_id: str, device_class: CoverDeviceClass | None
) -> None:
    """Test cover device classes."""
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class


async def test_close_cover(hass: HomeAssistant) -> None:
    """Test closing the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 70

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.CLOSING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_open_cover(hass: HomeAssistant) -> None:
    """Test opening the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPENING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_toggle_cover(hass: HomeAssistant) -> None:
    """Test toggling the cover."""
    # Start open
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes["current_position"] == 100
    # Toggle closed
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.TOGGLE,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    # Toggle open
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.TOGGLE,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_set_cover_position(hass: HomeAssistant) -> None:
    """Test moving the cover to a specific position."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 70

    # close to 10%
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_POSITION,
        {TargetKey.ENTITY_ID: ENTITY_COVER, CoverServiceArgument.POSITION: 10},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.CLOSING

    for _ in range(6):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 10
    assert state.state == CoverState.OPEN

    # open to 80%
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_POSITION,
        {TargetKey.ENTITY_ID: ENTITY_COVER, CoverServiceArgument.POSITION: 80},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPENING

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 80
    assert state.state == CoverState.OPEN


async def test_stop_cover(hass: HomeAssistant) -> None:
    """Test stopping the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.STOP,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 80
    assert state.state == CoverState.OPEN


async def test_close_cover_tilt(hass: HomeAssistant) -> None:
    """Test closing the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.CLOSING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


async def test_open_cover_tilt(hass: HomeAssistant) -> None:
    """Test opening the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPENING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        pytest.param(
            "cover.living_room_window",
            {
                CoverEntityCapabilityAttribute.OPEN_TILT_POSITION: 100,
                CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS: [0],
            },
            id="default",
        ),
        pytest.param(
            "cover.office_blind",
            {
                CoverEntityCapabilityAttribute.OPEN_TILT_POSITION: 50,
                CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS: [0, 100],
                CoverEntityCapabilityAttribute.TILT_START_ANGLE: -90,
                CoverEntityCapabilityAttribute.TILT_END_ANGLE: 90,
            },
            id="angles",
        ),
        pytest.param(
            "cover.pergola_roof",
            {
                CoverEntityCapabilityAttribute.OPEN_TILT_POSITION: 60,
                CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS: [0],
                CoverEntityCapabilityAttribute.TILT_START_ANGLE: -90,
                CoverEntityCapabilityAttribute.TILT_END_ANGLE: 60,
            },
            id="tilt_only",
        ),
    ],
)
async def test_tilt_capability_attributes(
    hass: HomeAssistant,
    entity_id: str,
    expected: dict[CoverEntityCapabilityAttribute, int | list[int]],
) -> None:
    """Test the tilt capability attributes."""
    state = hass.states.get(entity_id)
    assert state
    assert {
        attribute: state.attributes[attribute]
        for attribute in CoverEntityCapabilityAttribute
        if attribute in state.attributes
        and attribute is not CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS
    } == expected


@pytest.mark.parametrize(
    ("service", "tilt_position"),
    [
        pytest.param(CoverService.OPEN_TILT, 50, id="open"),
        pytest.param(CoverService.TOGGLE_TILT, 50, id="toggle"),
        pytest.param(CoverService.CLOSE_TILT, 0, id="close"),
    ],
)
async def test_tilt_with_open_position_in_the_middle(
    hass: HomeAssistant, service: str, tilt_position: int
) -> None:
    """Test the tilt of a cover that is open in the middle of the scale."""
    entity_id = "cover.office_blind"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100
    await hass.services.async_call(
        COVER_DOMAIN, service, {TargetKey.ENTITY_ID: entity_id}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == tilt_position


@pytest.mark.parametrize(
    ("entity_id", "tilt_position", "expected_state"),
    [
        pytest.param("cover.office_blind", 70, CoverState.OPENING, id="toward_open"),
        pytest.param("cover.pergola_roof", 100, CoverState.CLOSING, id="past_open"),
        pytest.param("cover.pergola_roof", 20, CoverState.CLOSING, id="toward_0"),
        pytest.param("cover.living_room_window", 80, CoverState.OPENING, id="default"),
    ],
)
async def test_set_tilt_position_moving_state(
    hass: HomeAssistant, entity_id: str, tilt_position: int, expected_state: str
) -> None:
    """Test the tilt opens when it moves toward the open tilt position."""
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {
            TargetKey.ENTITY_ID: entity_id,
            CoverServiceArgument.TILT_POSITION: tilt_position,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state


async def test_tilt_moving_state_across_the_open_position(
    hass: HomeAssistant,
) -> None:
    """Test a move between two closed positions reports closing all the way."""
    entity_id = "cover.office_blind"
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {TargetKey.ENTITY_ID: entity_id, CoverServiceArgument.TILT_POSITION: 0},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


async def test_open_tilt_stops_at_the_open_position(hass: HomeAssistant) -> None:
    """Test opening the tilt stops a move that passes the open position."""
    entity_id = "cover.office_blind"
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {TargetKey.ENTITY_ID: entity_id, CoverServiceArgument.TILT_POSITION: 0},
        blocking=True,
    )
    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN_TILT,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    for _ in range(3):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50


@pytest.mark.parametrize(
    "start_tilt_position",
    [
        pytest.param(70, id="from_70"),
        pytest.param(30, id="from_30"),
        pytest.param(50, id="from_the_open_position"),
        pytest.param(100, id="from_the_other_closed_position"),
    ],
)
async def test_close_tilt_always_goes_to_the_same_closed_position(
    hass: HomeAssistant, start_tilt_position: int
) -> None:
    """Test closing the tilt of a cover that is closed at both ends."""
    entity_id = "cover.office_blind"
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {
            TargetKey.ENTITY_ID: entity_id,
            CoverServiceArgument.TILT_POSITION: start_tilt_position,
        },
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


async def test_close_tilt_stops_a_move_from_the_closed_position(
    hass: HomeAssistant,
) -> None:
    """Test closing the tilt cancels a move that has not left the closed position."""
    entity_id = "cover.office_blind"
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {TargetKey.ENTITY_ID: entity_id, CoverServiceArgument.TILT_POSITION: 0},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN_TILT,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    for _ in range(3):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


async def test_tilt_only_cover_state(hass: HomeAssistant) -> None:
    """Test a cover without position is closed when its slats are closed."""
    entity_id = "cover.pergola_roof"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


async def test_toggle_cover_tilt(hass: HomeAssistant) -> None:
    """Test toggling the cover tilt."""
    # Start open
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100
    # Toggle closed
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.TOGGLE_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0
    # Toggle Open
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.TOGGLE_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_set_cover_tilt_position(hass: HomeAssistant) -> None:
    """Test moving the cover til to a specific position."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {TargetKey.ENTITY_ID: ENTITY_COVER, CoverServiceArgument.TILT_POSITION: 90},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPENING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 90


async def test_toggle_cover_during_tilt_move(hass: HomeAssistant) -> None:
    """Test toggling the cover stops a tilt move in progress."""
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.TOGGLE,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN

    for _ in range(3):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 40


async def test_stop_cover_tilt(hass: HomeAssistant) -> None:
    """Test stopping the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.STOP_TILT,
        {TargetKey.ENTITY_ID: ENTITY_COVER},
        blocking=True,
    )
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_COVER)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 40
