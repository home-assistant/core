"""Tests for REST config_flow.py."""

from http import HTTPStatus
from typing import Any

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.rest.const import (
    CONF_ENCODING,
    CONF_INITIAL_SUBENTRY_TYPE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_ICON,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .conftest import async_setup_entry

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_entry_and_subentries(
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "create_entry"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INITIAL_SUBENTRY_TYPE: Platform.BINARY_SENSOR},
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
        next_flow_id, get_subentry_data[0]["data"]
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
        {CONF_NAME: "test binary sensor"} | get_subentry_data[0]["data"],
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["unique_id"] == f"{Platform.BINARY_SENSOR}_2"
    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 2


@pytest.mark.usefixtures("async_mock_resource")
async def test_config_reconfigure_flow(
    hass: HomeAssistant, get_config_entry_data: dict[str, Any]
) -> None:
    """Test config entry reconfigure flow."""
    entry = await async_setup_entry(
        hass,
        get_config_entry_data,
    )
    assert entry.state == config_entries.ConfigEntryState.LOADED
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**get_config_entry_data, CONF_TIMEOUT: 15}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        hass.config_entries.async_get_known_entry(entry.entry_id).data[CONF_TIMEOUT]
        == 15
    )


async def test_subentry_reconfigure_flow(
    hass: HomeAssistant,
    async_setup_complete_entry: MockConfigEntry,
) -> None:
    """Test config entry reconfigure flow."""
    entry = async_setup_complete_entry
    assert entry.state == config_entries.ConfigEntryState.LOADED
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**subentry.data, CONF_ICON: "mdi:emoticon-happy"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        hass.config_entries.async_get_known_entry(entry.entry_id)
        .subentries[subentry.subentry_id]
        .data[CONF_ICON]
        == "mdi:emoticon-happy"
    )


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
    user_input = {
        **get_config_entry_data,
        CONF_ENCODING: "fake_encoding",
    }
    user_input[CONF_AUTHENTICATION][CONF_USERNAME] = "test_user"
    with pytest.raises(InvalidData) as ex:
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input)

    assert ex.value.schema_errors[CONF_ENCODING] == "codec not found"
    assert ex.value.schema_errors[CONF_AUTHENTICATION] == "credentials_missing"
