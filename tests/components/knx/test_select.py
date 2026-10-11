"""Test KNX select."""

import logging
from typing import Any

import pytest

from homeassistant.components.knx.const import (
    CONF_PAYLOAD_LENGTH,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    KNX_ADDRESS,
    SelectConf,
)
from homeassistant.components.knx.schema import SelectSchema
from homeassistant.const import CONF_NAME, CONF_PAYLOAD, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import mock_restore_cache
from tests.typing import WebSocketGenerator


async def test_select_dpt_2_simple(
    hass: HomeAssistant, knx: KNXTestKit, caplog: pytest.LogCaptureFixture
) -> None:
    """Test simple KNX select."""
    _options = [
        {CONF_PAYLOAD: 0b00, SelectConf.OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectConf.OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectConf.OPTION: "Control - On"},
    ]
    test_address = "1/1/1"
    await knx.setup_integration(
        {
            SelectSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: test_address,
                CONF_SYNC_STATE: False,
                CONF_PAYLOAD_LENGTH: 0,
                SelectConf.OPTIONS: _options,
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
    with caplog.at_level(logging.DEBUG):
        await knx.receive_write(test_address, 0b01)
    state = hass.states.get("select.test")
    assert state.state is STATE_UNKNOWN
    # the unconfigured payload and its telegram are logged for diagnosis
    assert any(
        "No option configured for payload 1 of select.test" in message
        and test_address in message
        for record in caplog.records
        if (message := record.getMessage())
    )

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
        {CONF_PAYLOAD: 0b00, SelectConf.OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectConf.OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectConf.OPTION: "Control - On"},
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
                SelectConf.OPTIONS: _options,
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
        {CONF_PAYLOAD: 0b00, SelectConf.OPTION: "No control"},
        {CONF_PAYLOAD: 0b10, SelectConf.OPTION: "Control - Off"},
        {CONF_PAYLOAD: 0b11, SelectConf.OPTION: "Control - On"},
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
                SelectConf.OPTIONS: _options,
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
        {CONF_PAYLOAD: 0, SelectConf.OPTION: "Auto"},
        {CONF_PAYLOAD: 1, SelectConf.OPTION: "Legio protect"},
        {CONF_PAYLOAD: 2, SelectConf.OPTION: "Normal"},
        {CONF_PAYLOAD: 3, SelectConf.OPTION: "Reduced"},
        {CONF_PAYLOAD: 4, SelectConf.OPTION: "Off"},
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
                SelectConf.OPTIONS: _options,
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


async def test_select_ui_create_custom_raw(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a select with custom raw options from the UI."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [
                    {"option": "No control", "payload": "0x0", "payload_length": 0},
                    {"option": "Control - Off", "payload": "0x2", "payload_length": 0},
                    {"option": "Control - On", "payload": "0x3", "payload_length": 0},
                ],
            },
            "sync_state": True,
        },
    )
    knx.assert_state("select.test", STATE_UNKNOWN)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Control - On"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", 0x3)
    knx.assert_state("select.test", "Control - On")

    # update from KNX
    await knx.receive_write("1/1/1", 0x2)
    knx.assert_state("select.test", "Control - Off")


async def test_select_ui_create_custom_typed(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a select with custom typed options for a DPT address."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "options_source": {
                "ga_custom": {"write": "1/1/1", "dpt": "5.010"},
                "custom_options": [
                    {"option": "Low", "value": 10},
                    {"option": "High", "value": 200},
                ],
            },
            "sync_state": True,
        },
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "High"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", (200,))
    knx.assert_state("select.test", "High")


async def test_select_ui_create_custom_mixed(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a select mixing typed and raw options for a DPT address."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "options_source": {
                "ga_custom": {"write": "1/1/1", "dpt": "5.010"},
                "custom_options": [
                    {"option": "Typed", "value": 10},
                    # raw payload matching the DPTs payload length
                    {"option": "Raw", "payload": "0x14", "payload_length": 1},
                ],
            },
            "sync_state": True,
        },
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Raw"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", (0x14,))
    knx.assert_state("select.test", "Raw")


async def test_select_ui_create_from_dpt(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a select whose options are derived from an enum DPT."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "options_source": {
                "ga_enum": {"write": "1/1/1", "state": "2/2/2", "dpt": "20.102"},
            },
            "sync_state": True,
        },
    )
    # options are derived from DPT 20.102 (HVAC operation mode)
    await knx.assert_read("2/2/2")
    await knx.receive_response("2/2/2", (1,))
    knx.assert_state("select.test", "comfort")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "standby"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", (2,))
    knx.assert_state("select.test", "standby")


async def test_select_ui_create_from_binary_dpt(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test a select derived from a binary enum DPT sending binary telegrams."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "options_source": {
                "ga_enum": {"write": "1/1/1", "state": "2/2/2", "dpt": "1.001"},
            },
            "sync_state": True,
        },
    )
    # DPT 1 is integrated in the APDU header - not sent as byte array
    await knx.assert_read("2/2/2", response=True)
    knx.assert_state("select.test", "on")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "off"},
        blocking=True,
    )
    await knx.assert_write("1/1/1", False)
    knx.assert_state("select.test", "off")


async def test_select_ui_create_custom_binary_dpt(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test custom options for a binary complex DPT."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SELECT,
        entity_data={"name": "test"},
        knx_data={
            "options_source": {
                "ga_custom": {"write": "1/1/1", "dpt": "2.001"},
                "custom_options": [
                    {
                        "option": "No control",
                        "value": {"control": False, "value": "off"},
                    },
                    {
                        "option": "Control - On",
                        "value": {"control": True, "value": "on"},
                    },
                ],
            },
            "sync_state": True,
        },
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.test", "option": "Control - On"},
        blocking=True,
    )
    # DPT 2.001 is a 2 bit payload - `control` and `value` bit set
    await knx.assert_write("1/1/1", 0b11)
    knx.assert_state("select.test", "Control - On")

    await knx.receive_write("1/1/1", 0b00)
    knx.assert_state("select.test", "No control")


async def test_select_ui_load(knx: KNXTestKit) -> None:
    """Test loading selects for both option sources from storage."""
    await knx.setup_integration(config_store_fixture="config_store_select.json")

    await knx.assert_read("2/2/2", response=0x2, ignore_order=True)
    knx.assert_state("select.test", "Control - Off")

    await knx.assert_read("4/4/4", response=(1,), ignore_order=True)
    knx.assert_state("select.from_dpt", "comfort")


@pytest.mark.parametrize(
    "knx_config",
    [
        {  # enum mode without a DPT
            "options_source": {"ga_enum": {"write": "1/1/1"}},
        },
        {  # enum mode with non-enum DPT
            "options_source": {"ga_enum": {"write": "1/1/1", "dpt": "5.001"}},
        },
        {  # custom mode without options
            "options_source": {"ga_custom": {"write": "1/1/1"}, "custom_options": []},
        },
        {  # custom raw options without payload length
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [{"option": "A", "payload": "0x1"}],
            },
        },
        {  # raw payload out of bound for length
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [
                    {"option": "A", "payload": "0x40", "payload_length": 0}
                ],
            },
        },
        {  # duplicate option name
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [
                    {"option": "A", "payload": "0x1", "payload_length": 1},
                    {"option": "A", "payload": "0x2", "payload_length": 1},
                ],
            },
        },
        {  # duplicate payload
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [
                    {"option": "A", "payload": "0x1", "payload_length": 1},
                    {"option": "B", "payload": "0x1", "payload_length": 1},
                ],
            },
        },
        {  # invalid typed value for DPT
            "options_source": {
                "ga_custom": {"write": "1/1/1", "dpt": "5.001"},
                "custom_options": [{"option": "A", "value": 101}],
            },
        },
        {  # payload lengths of options don't match each other
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [
                    {"option": "A", "payload": "0x1", "payload_length": 1},
                    {"option": "B", "payload": "0x1234", "payload_length": 2},
                ],
            },
        },
        {  # payload length doesn't match the DPT
            "options_source": {
                "ga_custom": {"write": "1/1/1", "dpt": "5.010"},
                "custom_options": [
                    {"option": "A", "payload": "0x1234", "payload_length": 2}
                ],
            },
        },
        {  # typed option without a DPT
            "options_source": {
                "ga_custom": {"write": "1/1/1"},
                "custom_options": [{"option": "A", "value": 1}],
            },
        },
    ],
)
async def test_select_ui_create_invalid(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    knx_config: dict[str, Any],
) -> None:
    """Test creating a select with invalid data."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": Platform.SELECT,
            "data": {
                "entity": {"name": "test"},
                "knx": knx_config,
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is False
