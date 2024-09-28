"""Test Matter covers."""

from math import floor
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.cover import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant

from .common import set_node_attribute, trigger_subscription_callback


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_lift", "cover.mock_lift_window_covering_cover"),
        ("window_covering_pa_lift", "cover.longan_link_wncv_da01_cover"),
        ("window_covering_tilt", "cover.mock_tilt_window_covering_cover"),
        ("window_covering_pa_tilt", "cover.mock_pa_tilt_window_covering_cover"),
        ("window_covering_full", "cover.mock_full_window_covering_cover"),
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_lift", "cover.mock_lift_window_covering_cover"),
        ("window_covering_pa_lift", "cover.longan_link_wncv_da01_cover"),
        ("window_covering_full", "cover.mock_full_window_covering_cover"),
    ],
)
async def test_cover_lift(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
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
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSING

    set_node_attribute(matter_node, 1, 258, 10, 0b000101)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPENING


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_lift", "cover.mock_lift_window_covering_cover"),
    ],
)
async def test_cover_lift_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
) -> None:
    """Test window covering devices with lift feature and without position aware lift feature."""

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2])
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] & CoverEntityFeature.SET_POSITION == 0

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2, 5])
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["supported_features"] & CoverEntityFeature.SET_POSITION != 0


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_pa_lift", "cover.longan_link_wncv_da01_cover"),
    ],
)
async def test_cover_position_aware_lift(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
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
        await trigger_subscription_callback(hass, matter_client)

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["current_position"] == 100 - floor(position / 100)
        assert state.state == STATE_OPEN

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["current_position"] == 0
    assert state.state == STATE_CLOSED


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_tilt", "cover.mock_tilt_window_covering_cover"),
        ("window_covering_pa_tilt", "cover.mock_pa_tilt_window_covering_cover"),
        ("window_covering_full", "cover.mock_full_window_covering_cover"),
    ],
)
async def test_cover_tilt(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
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

    await trigger_subscription_callback(hass, matter_client)

    set_node_attribute(matter_node, 1, 258, 10, 0b100010)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSING

    set_node_attribute(matter_node, 1, 258, 10, 0b010001)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPENING


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_tilt", "cover.mock_tilt_window_covering_cover"),
    ],
)
async def test_cover_tilt_only(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
) -> None:
    """Test window covering devices with tilt feature and without position aware tilt feature."""

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2])
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes["supported_features"] & CoverEntityFeature.SET_TILT_POSITION
        == 0
    )

    set_node_attribute(matter_node, 1, 258, 65529, [0, 1, 2, 8])
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.attributes["supported_features"] & CoverEntityFeature.SET_TILT_POSITION
        != 0
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("window_covering_pa_tilt", "cover.mock_pa_tilt_window_covering_cover"),
    ],
)
async def test_cover_position_aware_tilt(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
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
        await trigger_subscription_callback(hass, matter_client)

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["current_tilt_position"] == 100 - floor(
            tilt_position / 100
        )


@pytest.mark.parametrize("node_fixture", ["window_covering_full"])
async def test_cover_full_features(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test window covering devices with all the features."""
    entity_id = "cover.mock_full_window_covering_cover"

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
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 15, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN

    set_node_attribute(matter_node, 1, 258, 14, 5000)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 15, 5000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    set_node_attribute(matter_node, 1, 258, 14, 10000)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 15, 10000)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    set_node_attribute(matter_node, 1, 258, 14, None)
    set_node_attribute(matter_node, 1, 258, 15, None)
    set_node_attribute(matter_node, 1, 258, 10, 0b000000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"
