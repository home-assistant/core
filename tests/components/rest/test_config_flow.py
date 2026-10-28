"""Tests for REST config_flow.py."""

from http import HTTPStatus
from typing import Any

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant import config_entries
from homeassistant.components.rest.const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS_PATH,
    DOMAIN,
)
from homeassistant.components.sensor import CONF_STATE_CLASS, SensorDeviceClass
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_PARAMS,
    CONF_PAYLOAD,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfArea,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import async_setup_entry

BINARY_SENSOR_DATA = 0
SENSOR_DATA = 1


async def test_entry_and_binary_sensor_subentry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[config_entries.ConfigSubentryData],
) -> None:
    """Test the basic config flow and subentry flow."""

    aioclient_mock.get("http://localhost", exc=ClientError("client error"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        get_config_entry_data,
    )

    assert result["step_id"] == "user"

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "endpoint_error"}
    assert result["description_placeholders"] == {
        "endpoint_error_message": "client error"
    }

    aioclient_mock.clear_requests()

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"key": "on"},
        params={"fake_param": "fake_value"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        get_config_entry_data
        | {
            CONF_PAYLOAD: "test payload",
            CONF_PARAMS: [{"key": "fake_param", "value": "fake_value"}],
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.subentries.async_init(
        (result["result"].entry_id, Platform.BINARY_SENSOR),
        context=config_entries.SubentryFlowContext(source=config_entries.SOURCE_USER),
    )

    assert result["type"] == FlowResultType.FORM
    _, subentry_type = result["handler"]
    assert subentry_type is Platform.BINARY_SENSOR
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], get_subentry_data[BINARY_SENSOR_DATA]["data"]
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
    freezer: FrozenDateTimeFactory,
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

    freezer.tick(30)
    async_fire_time_changed(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, Platform.SENSOR),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout_error"


async def test_config_flow_subentry_flow_no_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test an entry and subentry flow with no data."""
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
    assert result["type"] == FlowResultType.FORM


async def test_sensor_subentry_flow_endpoint_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
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
    """Test a subentry flow for a resource error not handled by the coordinator or RestData."""
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
    assert result["reason"] == "endpoint_error"
    assert (
        "endpoint_error_message" in result["description_placeholders"]
        and "ZeroDivisionError"
        in result["description_placeholders"]["endpoint_error_message"]
    )


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
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], get_subentry_data[SENSOR_DATA]["data"]
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


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

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        get_subentry_data[SENSOR_DATA]["data"]
        | {
            CONF_DEVICE_CLASS: SensorDeviceClass.AREA,
            CONF_UNIT_OF_MEASUREMENT: UnitOfArea.SQUARE_METERS,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


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


async def test_xml_parse_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test that the subentry user flow handles ExpatErrors correctly."""

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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "xml_parse_error"

    await hass.config_entries.async_remove(entry.entry_id)

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

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        text='<?xml version="1.0" encoding="UTF-8"?><root><item>this was closed</item></root>',
        headers={"Content-Type": "application/xml"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


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

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"key": "on"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_config_flow_codec_not_found(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test that config_flow handles codec not found error."""
    aioclient_mock.get(
        "http://localhost", status=HTTPStatus.OK, json={"items": [{"key": "on"}]}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data | {CONF_ENCODING: "utf-88"}
    )

    assert (
        result["errors"]
        and CONF_ENCODING in result["errors"]
        and result["errors"][CONF_ENCODING] == "codec_not_found"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_config_flow_duplicate_configuration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
) -> None:
    """Test that duplicate resource config aborts the flow."""

    aioclient_mock.get(
        "http://localhost", status=HTTPStatus.OK, json={"items": [{"key": "on"}]}
    )

    entry = await async_setup_entry(hass, get_config_entry_data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.config_entries.async_remove(entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=config_entries.ConfigFlowContext(source=config_entries.SOURCE_USER),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], get_config_entry_data
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
