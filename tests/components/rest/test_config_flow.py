"""Tests for REST config_flow.py."""

from http import HTTPStatus
from typing import Any

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.rest.const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS_PATH,
    DOMAIN,
)
from homeassistant.components.sensor import CONF_STATE_CLASS, SensorDeviceClass
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_PARAMS,
    CONF_PAYLOAD,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    Platform,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .conftest import CONF_RESOURCE, async_setup_entry

from tests.test_util.aiohttp import AiohttpClientMocker

BINARY_SENSOR_DATA = 0
SENSOR_DATA = 1


async def test_entry_and_binary_sensor_subentry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test the basic config flow and subentry flow."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"key": "on"},
        params={"fake_param": "fake_value"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        get_config_entry_data
        | {
            CONF_PAYLOAD: "test payload",
            CONF_PARAMS: [{"key": "fake_param", "value": "fake_value"}],
        },
    )

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "subentries_menu"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": Platform.BINARY_SENSOR},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert result["result"].state == config_entries.ConfigEntryState.LOADED

    _, next_flow_id = result["next_flow"]

    result = await hass.config_entries.subentries.async_configure(next_flow_id)

    assert result["type"] == FlowResultType.FORM
    _, subentry_type = result["handler"]
    assert subentry_type is Platform.BINARY_SENSOR
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        next_flow_id, get_subentry_data[BINARY_SENSOR_DATA]["data"]
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    states = hass.states.async_all(Platform.BINARY_SENSOR)
    assert len(states) == 1
    assert states[0].state == "on"

    # Add second subentry to test unique id generation
    result = await hass.config_entries.subentries.async_init(
        result["handler"], context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[BINARY_SENSOR_DATA]["data"],
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["unique_id"] == f"{Platform.BINARY_SENSOR}_{result['flow_id']}"
    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 2


async def test_sensor_subentry_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test sensor subentry config flow."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"items": [{"key": "on", "location": "fake area", "area": 15}]},
    )
    entry = await async_setup_entry(hass, get_config_entry_data)
    assert entry.state == config_entries.ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], get_subentry_data[SENSOR_DATA]["data"]
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert len(entry.subentries) == 1

    states = hass.states.async_all()
    assert len(states) == 1
    state = states[0]
    assert "key" in state.attributes and "location" in state.attributes
    assert state.state == "15"
    assert state.entity_id == "sensor.rest_sensor"

    # regression test for second subentry
    aioclient_mock.clear_requests()
    aioclient_mock.get("http://localhost", exc=TimeoutError)

    await entry.runtime_data.async_refresh()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout_error"


async def test_config_flow_no_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test a entry and subentry flow with no data."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        text="",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )

    assert (
        result["errors"]
        and "base" in result["errors"]
        and result["errors"]["base"] == "no_json"
    )

    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    with pytest.raises(InvalidData) as ex:
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            get_subentry_data[SENSOR_DATA]["data"],
        )

    assert ex.value and ex.value.path == ["value_template"]
    assert "'value_json' is undefined" in ex.value.error_message


async def test_sensor_subentry_flow_endpoint_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test a subentry flow for a resource in error."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        text="",
    )
    entry = await async_setup_entry(hass, get_config_entry_data)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost",
        exc=ClientError("the server is down"),
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "endpoint_error"
    assert (
        result["description_placeholders"]
        and "endpoint_error_message" in result["description_placeholders"]
        and result["description_placeholders"]["endpoint_error_message"]
        == "the server is down"
    )


async def test_sensor_subentry_flow_payload_template_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test a subentry flow for a resource in error."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"key": "some_data"},
    )
    hass.states.async_set("sensor.dynamic", "1")
    entry = await async_setup_entry(
        hass,
        get_config_entry_data
        | {CONF_PAYLOAD: "{'a_value': {{ 1/(states('sensor.dynamic') | int) }}}"},
    )
    assert entry.state == config_entries.ConfigEntryState.LOADED
    hass.states.async_set("sensor.dynamic", "0")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER, "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "template_error"


async def test_sensor_subentry_flow_invalid_json_attrs_path(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test a subentry flow invalid json_attrs_path."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"items": [{"key": "on", "location": "fake area", "area": 15}]},
    )
    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"] | {CONF_JSON_ATTRS_PATH: "fake_path"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_result"}
    assert "json_path" in result["description_placeholders"]


async def test_sensor_subentry_flow_invalid_unit_state_class(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test a subentry flow with wrong unit/state class."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"items": [{"key": "on", "location": "fake area", "area": 15}]},
    )

    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"] | {CONF_UNIT_OF_MEASUREMENT: "$"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_UNIT_OF_MEASUREMENT] == "unit_validation_error"
    assert result["description_placeholders"]["unit"] == "$"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"]
        | {
            CONF_DEVICE_CLASS: SensorDeviceClass.WIND_DIRECTION,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_UNIT_OF_MEASUREMENT] == "unit_validation_error"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"]
        | {CONF_DEVICE_CLASS: SensorDeviceClass.MONETARY},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_STATE_CLASS] == "state_class_validation_error"
    assert result["description_placeholders"]["state_class"] == "measurement"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"]
        | {CONF_DEVICE_CLASS: SensorDeviceClass.DATE},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_STATE_CLASS] == "state_class_validation_error"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"]
        | {
            CONF_DEVICE_CLASS: SensorDeviceClass.GAS,
            CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_STATE_CLASS] == "state_class_validation_error"


async def test_subentry_flow_entry_not_loaded(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test to ensure subentry flow handles an entry with a state other than LOADED."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"items": [{"key": "on", "location": "fake area", "area": 15}]},
    )

    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state != config_entries.ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], get_subentry_data[SENSOR_DATA]["data"]
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_loaded"


async def test_invalid_rest_resource(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test config flow handling of resource (ClientError) handling."""
    aioclient_mock.get("http://localhost", exc=ClientError("client error"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        get_config_entry_data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "endpoint_error"}
    assert result["description_placeholders"] == {
        "endpoint_error_message": "client error"
    }


async def test_config_invalid_input(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test config entry flow schema validation."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = get_config_entry_data | {CONF_ENCODING: "fake_encoding"}
    user_input[CONF_AUTHENTICATION][CONF_USERNAME] = "test_user"
    with pytest.raises(InvalidData) as ex:
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input)

    assert ex.value.schema_errors[CONF_ENCODING] == "codec not found"
    assert ex.value.schema_errors[CONF_AUTHENTICATION] == "credentials_missing"


async def test_config_invalid_authentication_input(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test custom auth section schema handling."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = get_config_entry_data | {  # missing auth method
        CONF_AUTHENTICATION: {"extra_key": "fake_data"}
    }
    with pytest.raises(InvalidData) as ex:
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input)

    assert ex.value.error_message == "not a valid option"


async def test_config_template_error(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test template validation error handling."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(InvalidData) as ex:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            get_config_entry_data
            | {CONF_RESOURCE: "http://fakeurl.com/{{ param[5] }}"},
        )

    assert "UndefinedError" in ex.value.schema_errors[CONF_RESOURCE]


async def test_config_flow_template_error(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test template render error handling."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(InvalidData) as ex:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            get_config_entry_data
            | {CONF_HEADERS: [{"key": "Fake-Header", "value": "{{ 1/0 }}"}]},
        )

    assert (ex.value.path) == [CONF_HEADERS]
    assert "ZeroDivisionError" in str(ex.value.error_message)


async def test_xml_parse_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test if the subentry user flow handles ExpatErrors correctly."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        text='<?xml version="1.0" encoding="UTF-8"?><root><item>this was not closed</root>',
        headers={"Content-Type": "application/xml"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )
    assert result["type"] == FlowResultType.FORM
    assert (
        result["errors"]
        and "base" in result["errors"]
        and result["errors"]["base"] == "xml_parse_error"
    )
    assert (
        result["description_placeholders"]
        and "xml_parse_error_message" in result["description_placeholders"]
    )

    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "xml_parse_error"


async def test_config_flow_decode_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test that config_flow handles decode error as this is not handled by RestData."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, content=b"\x80")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )

    assert (
        result["errors"]
        and CONF_ENCODING in result["errors"]
        and result["errors"][CONF_ENCODING] == "decoding_error"
    )
    assert (
        "codec can't decode byte 0x80"
        in result["description_placeholders"]["decoding_error_message"]
    )
