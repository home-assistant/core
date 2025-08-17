"""Test KNX cover."""

from typing import Any

import pytest

from homeassistant.components.cover import CoverEntityFeature, CoverState
from homeassistant.components.knx.schema import CoverSchema
from homeassistant.const import CONF_NAME, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import async_capture_events


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

    # in KNX this will result in a payload of 191, percent values are encoded from 0 to 255
    # We need to transpile the position by using 100 - position due to the way KNX actuators work
    await knx.assert_write("1/0/3", (0xBF,))

    knx.assert_state(
        "cover.test",
        CoverState.CLOSING,
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

    # in KNX this will result in a payload of 191, percent values are encoded from 0 to 255
    # We need to transpile the position by using 100 - position due to the way KNX actuators work
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


@pytest.mark.parametrize(
    ("knx_data", "read_responses", "initial_state", "supported_features"),
    [
        (
            {
                "ga_up_down": {"write": "1/0/1"},
                "sync_state": True,
            },
            {},
            STATE_UNKNOWN,
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
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
    knx.assert_state("cover.test", initial_state, supported_features=supported_features)


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
