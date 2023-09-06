"""Test KNX button."""
from datetime import timedelta
import logging

import pytest

from homeassistant.components.knx.const import (
    CONF_PAYLOAD,
    CONF_PAYLOAD_LENGTH,
    DOMAIN,
    KNX_ADDRESS,
)
from homeassistant.components.knx.schema import ButtonSchema
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed


async def test_button_simple(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX button with default payload."""
    await knx.setup_integration(
        {
            ButtonSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
            }
        }
    )
    events = async_capture_events(hass, "state_changed")

    # press button
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", True)
    assert len(events) == 1
    events.pop()

    # received telegrams on button GA are ignored by the entity
    old_state = hass.states.get("button.test")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await knx.receive_write("1/2/3", False)
    await knx.receive_write("1/2/3", True)
    new_state = hass.states.get("button.test")
    assert old_state == new_state
    assert len(events) == 0

    # button does not respond to read
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_button_raw(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX button with raw payload."""
    await knx.setup_integration(
        {
            ButtonSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                CONF_PAYLOAD: False,
                CONF_PAYLOAD_LENGTH: 0,
            }
        }
    )
    # press button
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", False)


async def test_button_type(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX button with encoded payload."""
    await knx.setup_integration(
        {
            ButtonSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                ButtonSchema.CONF_VALUE: 21.5,
                CONF_TYPE: "2byte_float",
            }
        }
    )
    # press button
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (0x0C, 0x33))


@pytest.mark.parametrize(
    ("conf_type", "conf_value", "error_msg"),
    [
        (
            "2byte_float",
            "not_valid",
            "'payload: not_valid' not valid for 'type: 2byte_float'",
        ),
        (
            "not_valid",
            3,
            "type 'not_valid' is not a valid DPT identifier",
        ),
    ],
)
async def test_button_invalid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    knx: KNXTestKit,
    conf_type: str,
    conf_value: str,
    error_msg: str,
) -> None:
    """Test KNX button with configured payload that can't be encoded."""
    with caplog.at_level(logging.ERROR):
        await knx.setup_integration(
            {
                ButtonSchema.PLATFORM: {
                    CONF_NAME: "test",
                    KNX_ADDRESS: "1/2/3",
                    ButtonSchema.CONF_VALUE: conf_value,
                    CONF_TYPE: conf_type,
                }
            }
        )
        assert len(caplog.messages) == 2
        record = caplog.records[0]
        assert record.levelname == "ERROR"
        assert f"Invalid config for [knx]: {error_msg}" in record.message
        record = caplog.records[1]
        assert record.levelname == "ERROR"
        assert "Setup failed for knx: Invalid config." in record.message
    assert hass.states.get("button.test") is None
    assert hass.data.get(DOMAIN) is None
