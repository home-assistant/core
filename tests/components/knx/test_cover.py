"""Test KNX cover."""

import logging
from typing import Any

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.components.knx.const import CoverConf
from homeassistant.components.knx.schema import CoverSchema
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import async_capture_events, mock_restore_cache


async def test_cover_basic(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX cover basic."""
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_MOVE_SHORT_ADDRESS: "1/0/1",
                CoverSchema.CONF_POSITION_STATE_ADDRESS: "1/0/2",
                CoverSchema.CONF_POSITION_ADDRESS: "1/0/3",
            }
        }
    )
    events = async_capture_events(hass, "state_changed")

    # read position state address and angle state address
    await knx.assert_read("1/0/2")
    # StateUpdater initialize state
    await knx.receive_response("1/0/2", (0x0F,))
    events.clear()

    # open cover
    await hass.services.async_call(
        "cover", "open_cover", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/0", False)

    assert len(events) == 1
    events.pop()

    # close cover
    await hass.services.async_call(
        "cover", "close_cover", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/0", True)

    assert len(events) == 1
    events.pop()

    # stop cover
    await hass.services.async_call(
        "cover", "stop_cover", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/1", True)

    assert len(events) == 1
    events.pop()

    # set cover position
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"position": 25},
        target={"entity_id": "cover.test"},
        blocking=True,
    )

    # in KNX this will result in a payload of 191, percent values
    # are encoded from 0 to 255. We need to transpile the position
    # by using 100 - position due to the way KNX actuators work
    await knx.assert_write("1/0/3", (0xBF,))

    knx.assert_state(
        "cover.test",
        CoverState.CLOSING,
        assumed_state=None,
    )

    assert len(events) == 1
    events.pop()


async def test_cover_tilt_absolute(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX cover tilt."""
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_MOVE_SHORT_ADDRESS: "1/0/1",
                CoverSchema.CONF_POSITION_STATE_ADDRESS: "1/0/2",
                CoverSchema.CONF_POSITION_ADDRESS: "1/0/3",
                CoverSchema.CONF_ANGLE_STATE_ADDRESS: "1/0/4",
                CoverSchema.CONF_ANGLE_ADDRESS: "1/0/5",
            }
        }
    )
    events = async_capture_events(hass, "state_changed")

    # read position state address and angle state address
    await knx.assert_read("1/0/2")
    await knx.assert_read("1/0/4")
    # StateUpdater initialize state
    await knx.receive_response("1/0/2", (0x0F,))
    await knx.receive_response("1/0/4", (0x30,))
    events.clear()

    # set cover tilt position
    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"tilt_position": 25},
        target={"entity_id": "cover.test"},
        blocking=True,
    )

    # in KNX this will result in a payload of 191, percent values
    # are encoded from 0 to 255. We need to transpile the position
    # by using 100 - position due to the way KNX actuators work
    await knx.assert_write("1/0/5", (0xBF,))

    assert len(events) == 1
    events.pop()

    # close cover tilt
    await hass.services.async_call(
        "cover", "close_cover_tilt", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/5", (0xFF,))

    assert len(events) == 1
    events.pop()

    # open cover tilt
    await hass.services.async_call(
        "cover", "open_cover_tilt", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/5", (0x00,))


async def test_cover_tilt_move_short(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX cover tilt."""
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_MOVE_SHORT_ADDRESS: "1/0/1",
            }
        }
    )

    # close cover tilt
    await hass.services.async_call(
        "cover", "close_cover_tilt", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/1", 1)

    # open cover tilt
    await hass.services.async_call(
        "cover", "open_cover_tilt", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/1", 0)


async def test_cover_restore_assumed_state(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test a cover without position feedback restores its state and is assumed."""
    mock_restore_cache(
        hass,
        (
            State(
                "cover.test",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 40, ATTR_CURRENT_TILT_POSITION: 60},
            ),
        ),
    )
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_STOP_ADDRESS: "1/0/1",
                CoverSchema.CONF_ANGLE_ADDRESS: "1/0/2",
            }
        }
    )
    # position and tilt can't be read from the bus - no telegrams are sent
    await knx.assert_no_telegram()
    knx.assert_state(
        "cover.test",
        CoverState.OPEN,
        current_position=40,
        current_tilt_position=60,
        assumed_state=True,
    )


@pytest.mark.parametrize(
    "restored_state",
    [STATE_UNKNOWN, STATE_UNAVAILABLE],
)
async def test_cover_restore_unknown_state(
    hass: HomeAssistant, knx: KNXTestKit, restored_state: str
) -> None:
    """Test a cover doesn't restore a non-numeric position."""
    mock_restore_cache(
        hass,
        (State("cover.test", restored_state, {ATTR_CURRENT_POSITION: 40}),),
    )
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_STOP_ADDRESS: "1/0/1",
            }
        }
    )
    await knx.assert_no_telegram()
    knx.assert_state(
        "cover.test",
        STATE_UNKNOWN,
        current_position=None,
        assumed_state=True,
    )


async def test_cover_restore_readable(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test a readable cover shows the restored state until the bus read completes."""
    mock_restore_cache(
        hass,
        (State("cover.test", CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0}),),
    )
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_POSITION_STATE_ADDRESS: "1/0/2",
                CoverSchema.CONF_POSITION_ADDRESS: "1/0/3",
            }
        }
    )
    # restored value bridges the gap until the bus read completes - it is
    # assumed as long as it hasn't been confirmed by the bus
    knx.assert_state(
        "cover.test",
        CoverState.CLOSED,
        current_position=0,
        assumed_state=True,
    )
    # bus reports a different position - the confirmed value overwrites the
    # restored one and the state is no longer assumed
    await knx.assert_read("1/0/2", response=(0x00,))
    knx.assert_state(
        "cover.test",
        CoverState.OPEN,
        current_position=100,
        assumed_state=None,
    )


@pytest.mark.parametrize(
    ("knx_data", "read_responses", "initial_state", "supported_features", "assumed"),
    [
        (
            {
                "ga_up_down": {"write": "1/0/1"},
                "sync_state": True,
            },
            {},
            STATE_UNKNOWN,
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
            True,
        ),
        (
            {
                "ga_position_set": {"write": "2/0/1"},
                "ga_position_state": {"state": "2/0/0"},
                "sync_state": True,
            },
            {"2/0/0": (0x00,)},
            CoverState.OPEN,
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION,
            None,
        ),
        (
            {
                "ga_up_down": {"write": "3/0/1", "passive": []},
                "ga_stop": {"write": "3/0/2", "passive": []},
                "ga_position_set": {"write": "3/1/1", "passive": []},
                "ga_position_state": {"state": "3/1/0", "passive": []},
                "ga_angle": {"write": "3/2/1", "state": "3/2/0", "passive": []},
                "travelling_time_down": 16.0,
                "travelling_time_up": 16.0,
                "invert_angle": True,
                "sync_state": True,
            },
            {"3/1/0": (0x00,), "3/2/0": (0x00,)},
            CoverState.OPEN,
            CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.STOP
            | CoverEntityFeature.STOP_TILT,
            None,
        ),
    ],
)
async def test_cover_ui_create(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    knx_data: dict[str, Any],
    read_responses: dict[str, int | tuple[int]],
    initial_state: str,
    supported_features: int,
    assumed: bool | None,
) -> None:
    """Test creating a cover."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.COVER,
        entity_data={"name": "test"},
        knx_data=knx_data,
    )
    # created entity sends read-request to KNX bus
    for ga, value in read_responses.items():
        await knx.assert_read(ga, response=value, ignore_order=True)
    knx.assert_state(
        "cover.test",
        initial_state,
        supported_features=supported_features,
        assumed_state=assumed,
    )


async def test_cover_ui_load(knx: KNXTestKit) -> None:
    """Test loading a cover from storage."""
    await knx.setup_integration(config_store_fixture="config_store_cover.json")

    await knx.assert_read("2/0/0", response=(0xFF,), ignore_order=True)
    await knx.assert_read("3/1/0", response=(0xFF,), ignore_order=True)
    await knx.assert_read("3/2/0", response=(0xFF,), ignore_order=True)

    knx.assert_state(
        "cover.minimal",
        STATE_UNKNOWN,
        supported_features=CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN,
        assumed_state=True,
    )
    knx.assert_state(
        "cover.position_only",
        CoverState.OPEN,
        supported_features=CoverEntityFeature.CLOSE
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.SET_POSITION,
    )
    knx.assert_state(
        "cover.tiltable",
        CoverState.CLOSED,
        supported_features=CoverEntityFeature.CLOSE
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.STOP
        | CoverEntityFeature.STOP_TILT,
    )


async def test_cover_position_state_send(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test publishing the calculated position instead of listening on the address."""
    mock_restore_cache(
        hass,
        (State("cover.test", CoverState.OPEN, {ATTR_CURRENT_POSITION: 80}),),
    )
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_POSITION_STATE_ADDRESS: "1/0/2",
                CoverConf.POSITION_STATE_SEND: True,
                CoverConf.TRAVELLING_TIME_UP: 10,
                CoverConf.TRAVELLING_TIME_DOWN: 10,
            }
        }
    )
    # the restored position is published so a display can be answered before the
    # first travel - 80 % open is 20 % for KNX, 51 of 255
    await knx.assert_write("1/0/2", (0x33,))
    # Home Assistant is the sender here, so the address is never read
    await knx.assert_no_telegram()

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/0", True)


async def test_cover_position_state_send_inverted(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test the published value follows invert_position.

    The travel calculator counts 0 as open. With invert_position the group address
    counts the other way round, which xknx normally handles in the RemoteValueScaling
    ranges - the publishing device does not use those.
    """
    mock_restore_cache(
        hass,
        (State("cover.test", CoverState.OPEN, {ATTR_CURRENT_POSITION: 80}),),
    )
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_POSITION_STATE_ADDRESS: "1/0/2",
                CoverConf.POSITION_STATE_SEND: True,
                CoverConf.INVERT_POSITION: True,
            }
        }
    )
    # 80 % open is 20 % for the travel calculator - an inverted actuator expects 204
    await knx.assert_write("1/0/2", (0xCC,))


async def test_cover_position_state_send_is_not_a_state_address(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test a telegram on the address does not update the position.

    This is what caused a feedback loop with a manual `expose` configuration: Home
    Assistant read its own telegram back as actuator feedback.
    """
    mock_restore_cache(
        hass,
        (State("cover.test", CoverState.OPEN, {ATTR_CURRENT_POSITION: 80}),),
    )
    await knx.setup_integration(
        {
            CoverSchema.PLATFORM: {
                CONF_NAME: "test",
                CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                CoverSchema.CONF_POSITION_STATE_ADDRESS: "1/0/2",
                CoverConf.POSITION_STATE_SEND: True,
            }
        }
    )
    await knx.assert_write("1/0/2", (0x33,))

    await knx.receive_write("1/0/2", (0xFF,))
    state = hass.states.get("cover.test")
    assert state.attributes[ATTR_CURRENT_POSITION] == 80


async def test_cover_position_state_send_requires_address(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, knx: KNXTestKit
) -> None:
    """Test position_state_send without a position state address is rejected."""
    with caplog.at_level(logging.ERROR):
        await knx.setup_integration(
            {
                CoverSchema.PLATFORM: {
                    CONF_NAME: "test",
                    CoverSchema.CONF_MOVE_LONG_ADDRESS: "1/0/0",
                    CoverConf.POSITION_STATE_SEND: True,
                }
            }
        )
    assert "Invalid config for 'knx'" in caplog.text
    assert hass.states.get("cover.test") is None


async def test_cover_ui_position_state_send(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test publishing the position for a cover created from the UI."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.COVER,
        entity_data={"name": "test"},
        knx_data={
            "ga_up_down": {"write": "1/0/0"},
            "ga_position_state": {"state": "1/0/2"},
            CoverConf.POSITION_STATE_SEND: True,
            CoverConf.TRAVELLING_TIME_UP: 10,
            CoverConf.TRAVELLING_TIME_DOWN: 10,
        },
    )
    # the address is published to, so it is not read on creation
    await knx.assert_no_telegram()

    # and it is not a state address either - a telegram must not set the position
    await knx.receive_write("1/0/2", (0xFF,))
    state = hass.states.get("cover.test")
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None
