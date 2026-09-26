"""Tests for REST config_flow.py."""

from http import HTTPStatus
from typing import Any

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.rest.const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS,
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


async def test_sensor_subentry_flow_no_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test a subentry flow with no data."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        text="",
    )
    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"],
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_json"}


async def test_sensor_subentry_flow_invalid_json_attrs_path(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test a subentry flow wrong json_attrs_path."""
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
    assert (
        "'$' is not a valid unit"
        in result["description_placeholders"]["unit_validation_error_message"]
    )
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
    assert (
        "'measurement' is not a valid state class"
        in result["description_placeholders"]["state_class_validation_error_message"]
    )
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
        | {CONF_DEVICE_CLASS: SensorDeviceClass.GAS},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_STATE_CLASS] == "state_class_validation_error"


async def test_subentry_flow_entry_not_loaded(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test to ensure that a config entry entering any state other than LOADED is caught."""
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
    """Test any invalid resource."""
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
    assert result["description_placeholders"] == {"error_message": "client error"}


async def test_config_invalid_input(
    hass: HomeAssistant,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test config entry reconfigure flow."""

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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        get_config_entry_data
        | {CONF_HEADERS: [{"key": "Fake-Header", "value": "{{ 1/0 }}"}]},
    )

    assert (
        result["errors"]
        and "base" in result["errors"]
        and result["errors"]["base"] == "template_error"
    )


async def test_config_flow_xml_parse_error(
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

    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        (
            get_subentry_data[SENSOR_DATA]["data"]
            | {
                CONF_JSON_ATTRS_PATH: "$.root",
                CONF_JSON_ATTRS: [{"item": "item"}],
            }
        ),
    )

    assert (
        result["errors"]
        and "base" in result["errors"]
        and result["errors"]["base"] == "xml_parse_error"
    )
