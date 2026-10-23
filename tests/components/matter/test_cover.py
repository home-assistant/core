"""Test Matter covers."""

from math import floor
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.models.node import MatterNode
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import CoverEntityFeature, CoverState
from homeassistant.components.matter.cover import STATE_WRITE_DEBOUNCE_COOLDOWN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    set_node_attribute_and_notify,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


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
        ("mock_window_covering_pa_lift_null_tilt", "cover.shelly_2pm_gen4"),
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
        ("mock_window_covering_pa_lift_null_tilt", "cover.shelly_2pm_gen4"),
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

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 11, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    set_node_attribute(matter_node, 1, 258, 11, 0)
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
        ("mock_window_covering_pa_lift_null_tilt", "cover.shelly_2pm_gen4"),
    ],
)
async def test_cover_position_aware_lift_null_tilt(
    hass: HomeAssistant,
    matter_node: MatterNode,
    entity_id: str,
) -> None:
    """Test null tilt attribute while tilt is disabled (Shelly 2PM Gen4).

    See home-assistant/core#149876.
    """
    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes["supported_features"] & CoverEntityFeature.SET_TILT_POSITION
        == 0
    )
    assert "current_tilt_position" not in state.attributes


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
        ("mock_window_covering_full", "cover.mock_full_window_covering"),
    ],
)
async def test_cover_stale_moving_operational_status(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test moving operational status is ignored when the cover is at its target.

    Replays the Matter Server debug log of a Rademacher SmartHome Box bridged
    shutter (home-assistant/core#186168): resting at 42% lift with the tilt
    closed, it answers GoToLiftPercentage(10000) within ~100 ms with three
    attribute updates, OperationalStatus 0b001010, then target and current
    lift both 10000, and never reports the operational status clearing.
    """

    set_node_attribute(matter_node, 1, 258, 11, 4200)
    set_node_attribute(matter_node, 1, 258, 14, 4200)
    set_node_attribute(matter_node, 1, 258, 12, 10000)
    set_node_attribute(matter_node, 1, 258, 15, 10000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes["current_position"] == 58

    for attribute_id, value in (
        (10, 0b001010),
        (11, 10000),
        (14, 10000),
    ):
        await set_node_attribute_and_notify(
            hass,
            matter_client,
            matter_node,
            endpoint=1,
            cluster_id=258,
            attribute_id=attribute_id,
            value=value,
        )

    # no intermittent state is written while the report is still coalescing
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPEN

    freezer.tick(STATE_WRITE_DEBOUNCE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes["current_position"] == 0


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_full", "cover.mock_full_window_covering"),
    ],
)
async def test_cover_stale_moving_operational_status_since_interview(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale moving operational status is ignored across position reports.

    Replays the Matter Server debug log of a Rademacher SmartHome Box bridged
    venetian blind (home-assistant/core#186168): OperationalStatus 0b010101 as
    read at the interview is never reported again, neither on
    GoToLiftPercentage(10000) nor on GoToLiftPercentage(0). The bridge reports
    target and current lift as the same value on command receipt and during
    travel, except for one correction to the physical position 1.3 s after
    the open command.
    """

    set_node_attribute(matter_node, 1, 258, 10, 0b010101)
    set_node_attribute(matter_node, 1, 258, 11, 10000)
    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 12, 0)
    set_node_attribute(matter_node, 1, 258, 15, 0)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes["current_position"] == 0

    for updates, expected_state, expected_position in (
        # open command: target and current both reported as 0
        (((11, 0), (14, 0)), CoverState.OPEN, 100),
        # correction to the physical position: the status is trusted again
        (((14, 10000),), CoverState.OPENING, 0),
        # mid-travel report with target = current
        (((11, 7400), (14, 7400), (12, 1500), (15, 1500)), CoverState.OPEN, 26),
        # end of travel
        (((11, 0), (14, 0)), CoverState.OPEN, 100),
    ):
        for attribute_id, value in updates:
            await set_node_attribute_and_notify(
                hass,
                matter_client,
                matter_node,
                endpoint=1,
                cluster_id=258,
                attribute_id=attribute_id,
                value=value,
            )
        freezer.tick(STATE_WRITE_DEBOUNCE_COOLDOWN)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_state
        assert state.attributes["current_position"] == expected_position


@pytest.mark.parametrize(
    ("target_position", "current_position"),
    [
        pytest.param(None, 10000, id="unknown_target"),
        pytest.param(None, None, id="unknown_target_and_position"),
    ],
)
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
    ],
)
async def test_cover_moving_status_with_unknown_target(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
    target_position: int | None,
    current_position: int | None,
) -> None:
    """Test operational status is trusted when the positions cannot be compared."""

    set_node_attribute(matter_node, 1, 258, 11, target_position)
    set_node_attribute(matter_node, 1, 258, 14, current_position)
    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING


@pytest.mark.parametrize(
    (
        "node_fixture",
        "entity_id",
        "current_attribute_id",
        "target_attribute_id",
        "resting_state",
    ),
    [
        pytest.param(
            "mock_window_covering_pa_lift",
            "cover.longan_link_wncv_da01",
            14,
            11,
            CoverState.OPEN,
            id="lift",
        ),
        # a tilt only cover has no lift position to derive open/closed from
        pytest.param(
            "mock_window_covering_pa_tilt",
            "cover.mock_pa_tilt_window_covering",
            15,
            12,
            STATE_UNKNOWN,
            id="tilt",
        ),
        pytest.param(
            "mock_window_covering_full",
            "cover.mock_full_window_covering",
            14,
            11,
            CoverState.OPEN,
            id="lift_and_tilt_lift",
        ),
        pytest.param(
            "mock_window_covering_full",
            "cover.mock_full_window_covering",
            15,
            12,
            CoverState.OPEN,
            id="lift_and_tilt_tilt",
        ),
    ],
)
async def test_cover_target_position_subscription(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    current_attribute_id: int,
    target_attribute_id: int,
    resting_state: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a target position only report reaches the entity."""

    set_node_attribute(matter_node, 1, 258, current_attribute_id, 4900)
    set_node_attribute(matter_node, 1, 258, target_attribute_id, 0)
    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    # StopMotion sets the target to the current position, so a target only
    # report is enough to clear a stale moving operational status
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=258,
        attribute_id=target_attribute_id,
        value=4900,
    )
    freezer.tick(STATE_WRITE_DEBOUNCE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == resting_state


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
    ],
)
async def test_cover_moving_status_masked_until_target_updates(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a moving operational status is ignored while the target is stale."""

    # the cover rests at its target and starts moving, but the report carries
    # only the operational status, so the stale target masks the movement
    set_node_attribute(matter_node, 1, 258, 11, 10000)
    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000101)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSED

    # the movement is reported again once the target catches up
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=258,
        attribute_id=11,
        value=0,
    )
    freezer.tick(STATE_WRITE_DEBOUNCE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.OPENING


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_pa_lift", "cover.longan_link_wncv_da01"),
    ],
)
async def test_cover_position_updates_without_operational_status(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device which only reports positions, never an operational status."""

    # the device reports the new target and position updates while the
    # operational status remains "not moving" the whole time
    set_node_attribute(matter_node, 1, 258, 11, 10000)
    set_node_attribute(matter_node, 1, 258, 14, 5000)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 50
    assert state.state == CoverState.OPEN

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

    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 12, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b100010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING

    set_node_attribute(matter_node, 1, 258, 12, 0)
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


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "feature_map", "expected_state"),
    [
        # a covering that tilts without being position aware on tilt: the lift
        # sitting at its target says nothing about whether the tilt is moving
        pytest.param(
            "mock_window_covering_pa_lift",
            "cover.longan_link_wncv_da01",
            0b00111,
            CoverState.CLOSING,
            id="tilt_not_position_aware",
        ),
        # the same, with tilt positions exposed regardless
        pytest.param(
            "mock_window_covering_full",
            "cover.mock_full_window_covering",
            0b00111,
            CoverState.CLOSING,
            id="tilt_not_position_aware_positions_exposed",
        ),
        # a covering which is not position aware on lift but exposes lift
        # positions regardless
        pytest.param(
            "mock_window_covering_pa_lift",
            "cover.longan_link_wncv_da01",
            0b00001,
            CoverState.CLOSING,
            id="lift_not_position_aware_positions_exposed",
        ),
        # a covering claiming to be position aware on tilt without exposing
        # the tilt position attributes
        pytest.param(
            "mock_window_covering_pa_lift",
            "cover.longan_link_wncv_da01",
            0b10111,
            CoverState.CLOSING,
            id="tilt_positions_missing",
        ),
        # the Shelly 2PM Gen4 exposes null tilt positions without supporting
        # tilt, which must not keep the lift from being checked
        pytest.param(
            "mock_window_covering_pa_lift_null_tilt",
            "cover.shelly_2pm_gen4",
            0b00101,
            CoverState.CLOSED,
            id="tilt_unsupported_null_positions",
        ),
    ],
)
async def test_cover_moving_status_axis_selection(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    feature_map: int,
    expected_state: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the axes compared against their target follow the FeatureMap."""

    set_node_attribute(matter_node, 1, 258, 65532, feature_map)
    set_node_attribute(matter_node, 1, 258, 11, 10000)
    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("mock_window_covering_full", "cover.mock_full_window_covering"),
    ],
)
async def test_cover_moving_status_with_unknown_tilt_position(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the lift at its target does not hide movement with an unknown tilt."""

    set_node_attribute(matter_node, 1, 258, 11, 10000)
    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 12, 0)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b001010)
    await trigger_subscription_callback_debounced(hass, freezer, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == CoverState.CLOSING
