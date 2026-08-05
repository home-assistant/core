"""Test KNX select."""

import pytest

from homeassistant.components.knx.const import (
    CONF_PAYLOAD_LENGTH,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    KNX_ADDRESS,
)
from homeassistant.components.knx.schema import SelectSchema
from homeassistant.const import CONF_NAME, CONF_PAYLOAD, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import mock_restore_cache
from tests.typing import WebSocketGenerator


async def test_select_dpt_2_simple(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test simple KNX select."""
    _options = [
        {CONF_PAYLOAD: 0b00, SelectSchema.CONF_OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectSchema.CONF_OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectSchema.CONF_OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_SYNC_STATE: False,
                CONF_PAYLOAD_LENGTH: 0,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN

    # select an option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Control - Off"},
        blocking=True,
    )
    await knx.assert_write(test_address, 0b10)
    state = hass.states.get("select.test")
    assert state.state == "Control - Off"

    # select another option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "No control"},
        blocking=True,
    )
    await knx.assert_write(test_address, 0b00)
    state = hass.states.get("select.test")
    assert state.state == "No control"

    # don't answer to GroupValueRead requests by default
    await knx.receive_read(test_address)
    await knx.assert_no_telegram()

    # update from KNX
    await knx.receive_write(test_address, 0b11)
    state = hass.states.get("select.test")
    assert state.state == "Control - On"

    # update from KNX with undefined value
    await knx.receive_write(test_address, 0b01)
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN

    # select invalid option
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": "select.test", "option": "invalid"},
            blocking=True,
        )
    await knx.assert_no_telegram()


async def test_select_dpt_2_restore(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX select with passive_address and respond_to_read restoring state."""
    _options = [
        {CONF_PAYLOAD: 0b00, SelectSchema.CONF_OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectSchema.CONF_OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectSchema.CONF_OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    test_passive_address = "3/3/3"
    fake_state = State("select.test", "Control - On")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_RESPOND_TO_READ: True,
                CONF_PAYLOAD_LENGTH: 0,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    # restored state - doesn't send telegram
    state = hass.states.get("select.test")
    assert state.state == "Control - On"
    await knx.assert_telegram_count(0)

    # respond with restored state
    await knx.receive_read(test_address)
    await knx.assert_response(test_address, 3)

    # don't respond to passive address
    await knx.receive_read(test_passive_address)
    await knx.assert_no_telegram()


async def test_select_state_restore(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX select with state_address restores state until bus read completes."""
    _options = [
        {CONF_PAYLOAD: 0b00, SelectSchema.CONF_OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectSchema.CONF_OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectSchema.CONF_OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    test_state_address = "2/2/2"
    fake_state = State("select.test", "Control - On")
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_STATE_ADDRESS: test_state_address,
                CONF_PAYLOAD_LENGTH: 0,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    # StateUpdater initialize state - restored value is used before response is received
    await knx.assert_read(test_state_address)
    state = hass.states.get("select.test")
    assert state.state == "Control - On"

    # bus reports a different value than restored - state updates to the real value
    await knx.receive_response(test_state_address, 0b10)
    state = hass.states.get("select.test")
    assert state.state == "Control - Off"


async def test_select_dpt_20_103_all_options(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX select with state_address, passive_address and respond_to_read."""
    _options = [
        {CONF_PAYLOAD: 0, SelectSchema.CONF_OPTION: "Auto"},
        {CONF_PAYLOAD: 1, SelectSchema.CONF_OPTION: "Legio protect"},
        {CONF_PAYLOAD: 2, SelectSchema.CONF_OPTION: "Normal"},
        {CONF_PAYLOAD: 3, SelectSchema.CONF_OPTION: "Reduced"},
        {CONF_PAYLOAD: 4, SelectSchema.CONF_OPTION: "Off"},
    ]
    test_address = "1/1/1"
    test_state_address = "2/2/2"
    test_passive_address = "3/3/3"

    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: [test_address, test_passive_address],
                CONF_STATE_ADDRESS: test_state_address,
                CONF_RESPOND_TO_READ: True,
                CONF_PAYLOAD_LENGTH: 1,
                SelectSchema.CONF_OPTIONS: _options,
            }
        }
    )
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN

    # StateUpdater initialize state
    await knx.assert_read(test_state_address)
    await knx.receive_response(test_state_address, (2,))
    state = hass.states.get("select.test")
    assert state.state == "Normal"

    # select an option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Legio protect"},
        blocking=True,
    )
    await knx.assert_write(test_address, (1,))
    state = hass.states.get("select.test")
    assert state.state == "Legio protect"

    # answer to GroupValueRead requests
    await knx.receive_read(test_address)
    await knx.assert_response(test_address, (1,))

    # update from KNX state_address
    await knx.receive_write(test_state_address, (3,))
    state = hass.states.get("select.test")
    assert state.state == "Reduced"

    # update from KNX passive_address
    await knx.receive_write(test_passive_address, (4,))
    state = hass.states.get("select.test")
    assert state.state == "Off"


async def test_select_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test a select created from the UI - forced control of a shutter (DPT 2)."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "ga_select": {"write": "1/1/1", "state": "2/2/2"},
            "payload_length": 0,
            "options": [
                {"option": "No control", "payload": 0},
                {"option": "Force up", "payload": 2},
                {"option": "Force down", "payload": 3},
            ],
            "respond_to_read": False,
            "sync_state": True,
        },
    )
    await knx.assert_read("2/2/2")
    await knx.receive_response("2/2/2", 2)
    knx.assert_state("select.test", "Force up")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Force down"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", 3)
    knx.assert_state("select.test", "Force down")


@pytest.mark.parametrize(
    ("options", "error_start"),
    [
        (
            [{"option": "A", "payload": 0}, {"option": "A", "payload": 1}],
            "duplicate item for 'option' not allowed: A",
        ),
        (
            [{"option": "A", "payload": 1}, {"option": "B", "payload": 1}],
            "duplicate item for 'payload' not allowed: 1",
        ),
        (
            [{"option": "A", "payload": 64}],
            "'payload: 64' for 'option: A' exceeds possible maximum",
        ),
        (
            # coerced to an int first, so the maximum is reported, not a type error
            [{"option": "A", "payload": "70"}],
            "'payload: 70' for 'option: A' exceeds possible maximum",
        ),
    ],
    ids=[
        "duplicate_option",
        "duplicate_payload",
        "payload_too_large",
        "payload_string_too_large",
    ],
)
async def test_select_ui_invalid_options(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    options: list[dict[str, str | int]],
    error_start: str,
) -> None:
    """Test the UI schema rejects options that can not be told apart."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "knx/validate_entity",
            "platform": Platform.SELECT,
            "data": {
                "entity": {"name": "test"},
                "knx": {
                    "ga_select": {"write": "1/1/1"},
                    "payload_length": 0,
                    "options": options,
                },
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is False
    assert res["result"]["error_base"].startswith(error_start)


async def test_select_ui_payload_is_coerced_to_int(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test non-integer payloads are truncated, like cv.positive_int does for YAML."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "ga_select": {"write": "1/1/1"},
            "payload_length": 0,
            # the number field in the frontend allows this - it must not reach xknx
            "options": [
                {"option": "A", "payload": 1.0},
                {"option": "B", "payload": 2.5},
            ],
        },
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "B"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", 2)
    knx.assert_state("select.test", "B")


async def test_select_ui_update(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a stored configuration can be read back and saved again unchanged."""
    await knx.setup_integration()
    entity = await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "ga_select": {"write": "1/1/1"},
            "payload_length": 0,
            "options": [{"option": "A", "payload": 0}, {"option": "B", "payload": 2}],
        },
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "knx/get_entity_config", "entity_id": entity.entity_id}
    )
    res = await client.receive_json()
    assert res["success"], res
    stored = res["result"]["data"]

    await client.send_json_auto_id(
        {
            "type": "knx/update_entity",
            "platform": Platform.SELECT,
            "entity_id": entity.entity_id,
            "data": stored,
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is True, res["result"]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity.entity_id, "option": "B"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", 2)
