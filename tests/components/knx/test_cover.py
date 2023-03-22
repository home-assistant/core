"""Test KNX cover."""

from homeassistant.components.knx.schema import CoverSchema
from homeassistant.const import CONF_NAME, STATE_CLOSING
from homeassistant.core import HomeAssistant

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
        STATE_CLOSING,
    )

    assert len(events) == 1
    events.pop()

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
    await knx.assert_write("1/0/1", True)

    assert len(events) == 1
    events.pop()

    # open cover tilt
    await hass.services.async_call(
        "cover", "open_cover_tilt", target={"entity_id": "cover.test"}, blocking=True
    )
    await knx.assert_write("1/0/1", False)
