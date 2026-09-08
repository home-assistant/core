"""Test KNX button."""

from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.knx.const import (
    CONF_PAYLOAD_LENGTH,
    CONF_VALUE,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
)
from homeassistant.components.knx.schema import ButtonSchema
from homeassistant.const import (
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_TYPE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_button_simple(
    hass: HomeAssistant, knx: KNXTestKit, freezer: FrozenDateTimeFactory
) -> None:
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
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
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
                CONF_VALUE: 21.5,
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
                    CONF_VALUE: conf_value,
                    CONF_TYPE: conf_type,
                }
            }
        )
        assert len(caplog.messages) == 2
        record = caplog.records[0]
        assert record.levelname == "ERROR"
        assert f"Invalid config for 'knx': {error_msg}" in record.message
        record = caplog.records[1]
        assert record.levelname == "ERROR"
        assert "Setup failed for 'knx': Invalid config." in record.message
    assert hass.states.get("button.test") is None
    assert hass.data.get(KNX_MODULE_KEY) is None


@pytest.mark.parametrize(
    "knx_config",
    [
        (
            {
                "ga_send": {"write": "1/1/1"},
                "data": {"payload": "1", "payload_length": 1},  # raw payload
            }
        ),
        (
            {
                "ga_send": {"write": "1/1/1", "dpt": "5"},  # generic 1byte uint
                "data": {"payload": "0x01", "payload_length": 1},  # raw payload
            }
        ),
        (
            {
                "ga_send": {"write": "1/1/1", "dpt": "5"},  # generic 1byte uint
                "data": {"value": 1},  # typed value
            }
        ),
    ],
)
async def test_button_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    knx_config: dict[str, Any],
) -> None:
    """Test creating a button."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.BUTTON,
        entity_data={"name": "test"},
        knx_data=knx_config,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test"}, blocking=True
    )
    await knx.assert_write("1/1/1", (1,))


async def test_button_ui_load(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test loading a button from storage."""
    await knx.setup_integration(config_store_fixture="config_store_button.json")

    # Raw button configuration
    knx.assert_state(
        "button.test_raw",
        STATE_UNKNOWN,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_raw"}, blocking=True
    )
    await knx.assert_write("1/1/1", (1,))

    # Typed button configuration
    knx.assert_state(
        "button.test_typed",
        STATE_UNKNOWN,
    )
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_typed"}, blocking=True
    )
    await knx.assert_write("1/1/2", True)


@pytest.mark.parametrize(
    "knx_config",
    [
        {  # missing data
            "ga_send": {"write": "1/1/1", "dpt": "9.001"},
        },
        {  # missing DPT
            "ga_send": {"write": "1/1/1"},
            "data": {"value": 1},
        },
        {  # invalid value for DPT
            "ga_send": {"write": "1/1/1", "dpt": "9.001"},
            "data": {"value": "not_valid"},
        },
        {  # invalid length for DPT
            "ga_send": {"write": "1/1/1", "dpt": "9.001"},
            "data": {"payload": "0x1", "payload_length": 1},
        },
        {  # out of bound value for DPT
            "ga_send": {"write": "1/1/1", "dpt": "5.001"},
            "data": {"value": 101},
        },
        {  # out of bound value for length
            "ga_send": {"write": "1/1/1"},
            "data": {"payload": "0x100", "payload_length": 1},
        },
        {  # out of bound value for zero-length
            "ga_send": {"write": "1/1/1"},
            "data": {"payload": "0x40", "payload_length": 0},
        },
    ],
)
async def test_button_ui_create_data_validation(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    knx_config: dict[str, Any],
) -> None:
    """Test creating a button with invalid data."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": Platform.BUTTON,
            "data": {
                "entity": {"name": "test"},
                "knx": knx_config,
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is False
    assert res["result"]["error_base"]
    assert res["result"]["errors"][0]["path"]
