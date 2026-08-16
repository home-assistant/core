"""Test Matter covers."""

from math import floor
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.components.matter.cover import STATE_WRITE_DEBOUNCE_COOLDOWN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

from tests.common import async_fire_time_changed


async def trigger_subscription_callback_debounced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
) -> None:
    """Trigger subscription callbacks and wait for the debounced state write."""
    await trigger_subscription_callback(hass, client)
    freezer.tick(STATE_WRITE_DEBOUNCE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("matter_devices")
async def test_covers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test covers."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.COVER)


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_lift", "cover.mock_lift_window_covering"),
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
        ("mock_window_covering_tilt", "cover.mock_tilt_window_covering"),
        ("mock_window_covering_pa_tilt", "cover.mock_pa_tilt_window_covering"),
        ("mock_window_covering_full", "cover.mock_full_window_covering"),
    ],
)
async def test_cover(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
) -> None:
    """Test window covering commands that always are implemented."""

    await hass.services.async_call(
        "cover",
        "close_cover",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.DownOrClose(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.StopMotion(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "open_cover",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.UpOrOpen(),
    )
    matter_client.send_device_command.reset_mock()


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_lift", "cover.mock_lift_window_covering"),
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
        ("mock_window_covering_full", "cover.mock_full_window_covering"),
    ],
)
async def test_cover_lift(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering devices with lift and position aware lift features."""
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {
            "entity_id": entity_id,
            "position": 50,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.GoToLiftPercentage(5000),
    )
    matter_client.send_device_command.reset_mock()

    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    set_node_attribute(matter_node, 1, 258, 10, 0b000101)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPENING


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_lift", "cover.mock_lift_window_covering"),
    ],
)
async def test_cover_lift_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering with lift but without position aware lift."""

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2])
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] & CoverEntityFeature.SET_POSITION == 0

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2, 5])
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] & CoverEntityFeature.SET_POSITION != 0


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
    ],
)
async def test_cover_position_aware_lift(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering devices with position aware lift features."""

    state = hass.states.get(entity_id)
    assert state
    mask = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    assert state.attributes["supported_features"] & mask == mask

    for position in (0, 9999):
        set_node_attribute(matter_node, 1, 258, 14, position)
        set_node_attribute(matter_node, 1, 258, 10, 0b000000)
        await trigger_subscription_callback_debounced(hass, freezer, matter_client)

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["current_position"] == 100 - floor(position / 100)
        assert state.state == CoverState.OPEN

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 0
    assert state.state == CoverState.CLOSED


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
    ],
)
async def test_cover_split_attribute_updates(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test state writes are debounced to coalesce split attribute updates."""

    set_node_attribute(matter_node, 1, 258, 14, 9900)
    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    # the device reports it stopped moving, while the final position
    # arrives as a separate attribute update slightly later
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)

    # the intermittent state (stopped at 1% open) is not written
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 0
    assert state.state == CoverState.CLOSED


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_tilt", "cover.mock_tilt_window_covering"),
        ("mock_window_covering_pa_tilt", "cover.mock_pa_tilt_window_covering"),
        ("mock_window_covering_full", "cover.mock_full_window_covering"),
    ],
)
async def test_cover_tilt(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering devices with tilt and position aware tilt features."""

    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {
            "entity_id": entity_id,
            "tilt_position": 50,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.GoToTiltPercentage(5000),
    )
    matter_client.send_device_command.reset_mock()

    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    set_node_attribute(matter_node, 1, 258, 10, 0b100010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    set_node_attribute(matter_node, 1, 258, 10, 0b010001)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPENING


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_tilt", "cover.mock_tilt_window_covering"),
    ],
)
async def test_cover_tilt_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering with tilt but without position aware tilt."""

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2])
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes["supported_features"] & CoverEntityFeature.SET_TILT_POSITION
        == 0
    )

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2, 8])
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes["supported_features"] & CoverEntityFeature.SET_TILT_POSITION
        != 0
    )


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_pa_tilt", "cover.mock_pa_tilt_window_covering"),
    ],
)
async def test_cover_position_aware_tilt(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering devices with position aware tilt feature."""

    state = hass.states.get(entity_id)
    assert state
    mask = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_TILT_POSITION
    )
    assert state.attributes["supported_features"] & mask == mask

    for tilt_position in (0, 9999, 10000):
        set_node_attribute(matter_node, 1, 258, 15, tilt_position)
        set_node_attribute(matter_node, 1, 258, 10, 0b000000)
        await trigger_subscription_callback_debounced(hass, freezer, matter_client)

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["current_tilt_position"] == 100 - floor(
            tilt_position / 100
        )


@pytest.mark.parametrize("node_fixture", ["mock_window_covering_full"])
async def test_cover_full_features(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test window covering devices with all the features."""
    entity_id = "cover.mock_full_window_covering"

    state = hass.states.get(entity_id)
    assert state
    mask = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.SET_TILT_POSITION
    )
    assert state.attributes["supported_features"] & mask == mask

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 15, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 15, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 15, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"


@pytest.mark.parametrize("node_fixture", ["mock_closure_garage_door"])
async def test_closure_cover_garage_door(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a single-endpoint Closure (garage door, no ClosurePanel children)."""
    cover_states = hass.states.async_all(Platform.COVER)
    assert len(cover_states) == 1
    entity_id = cover_states[0].entity_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes["device_class"] == CoverDeviceClass.GARAGE

    supported_mask = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    assert state.attributes["supported_features"] & supported_mask == supported_mask
    # no ClosurePanel children on this fixture: no fine position control
    assert (
        state.attributes["supported_features"]
        & (CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION)
        == 0
    )

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        # this fixture doesn't support MotionLatching: no `latch` kwarg
        command=clusters.ClosureControl.Commands.MoveTo(
            position=clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyClosed
        ),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ClosureControl.Commands.MoveTo(
            position=clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyOpen
        ),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ClosureControl.Commands.Stop(),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    set_node_attribute(
        matter_node,
        1,
        clusters.ClosureControl.id,
        clusters.ClosureControl.Attributes.MainState.attribute_id,
        clusters.ClosureControl.Enums.MainStateEnum.kMoving.value,
    )
    set_node_attribute(
        matter_node,
        1,
        clusters.ClosureControl.id,
        clusters.ClosureControl.Attributes.OverallTargetState.attribute_id,
        {0: clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyClosed.value},
    )
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING


@pytest.mark.parametrize("node_fixture", ["mock_closure_venetian_blinds"])
async def test_closure_cover_venetian_blinds(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a multi-panel Closure: Lift + Tilt ClosurePanel child endpoints."""
    cover_states = hass.states.async_all(Platform.COVER)
    assert len(cover_states) == 1
    entity_id = cover_states[0].entity_id

    state = hass.states.get(entity_id)
    assert state
    # BLIND because of the "Covering.Venetian" semantic tag on the parent endpoint
    assert state.attributes["device_class"] == CoverDeviceClass.BLIND
    assert state.state == CoverState.CLOSED

    supported_mask = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.SET_TILT_POSITION
    )
    assert state.attributes["supported_features"] & supported_mask == supported_mask

    # both panels' initial CurrentState.position is 10000 (percent100ths, closed)
    assert state.attributes["current_position"] == 0
    assert state.attributes["current_tilt_position"] == 0

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        # this fixture supports MotionLatching: MoveTo always specifies `latch`
        command=clusters.ClosureControl.Commands.MoveTo(
            position=clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyClosed,
            latch=False,
        ),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ClosureControl.Commands.MoveTo(
            position=clusters.ClosureControl.Enums.TargetPositionEnum.kMoveToFullyOpen,
            latch=False,
        ),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    # Lift position is commanded on endpoint 2, the child ClosurePanel tagged "Lift"
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 30},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=2,
        # this panel supports MotionLatching: SetTarget always specifies `latch`,
        # unlatching it as part of the move (a latched panel rejects SetTarget
        # with InvalidInState otherwise)
        command=clusters.ClosureDimension.Commands.SetTarget(
            position=7000, latch=False
        ),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    # Tilt position is commanded on endpoint 3, the child ClosurePanel tagged "Tilt"
    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": entity_id, "tilt_position": 30},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=3,
        command=clusters.ClosureDimension.Commands.SetTarget(
            position=7000, latch=False
        ),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    # a panel that doesn't support MotionLatching gets no `latch` kwarg at all
    set_node_attribute(
        matter_node,
        2,
        clusters.ClosureDimension.id,
        clusters.ClosureDimension.Attributes.FeatureMap.attribute_id,
        95 & ~clusters.ClosureDimension.Bitmaps.Feature.kMotionLatching,
    )
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 30},
        blocking=True,
    )
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=2,
        command=clusters.ClosureDimension.Commands.SetTarget(position=7000),
        timed_request_timeout_ms=1000,
    )
    matter_client.send_device_command.reset_mock()

    # attribute updates on the child panels (not the parent) update position/tilt
    set_node_attribute(
        matter_node,
        2,
        clusters.ClosureDimension.id,
        clusters.ClosureDimension.Attributes.CurrentState.attribute_id,
        {0: 7000, 1: True, 2: 0},
    )
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 30
    assert state.attributes["current_tilt_position"] == 0

    set_node_attribute(
        matter_node,
        3,
        clusters.ClosureDimension.id,
        clusters.ClosureDimension.Attributes.CurrentState.attribute_id,
        {0: 2000, 1: True, 2: 0},
    )
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 30
    assert state.attributes["current_tilt_position"] == 80
