"""Test the swiss_public_transport config flow."""
from unittest.mock import AsyncMock

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.swiss_public_transport import config_flow
from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


# async def test_flow_user_init(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
#     """Test the initialization of the form in the first step of the config flow."""
#     aioclient_mock.get(
#         "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
#         json={"from": "test_start", "to": "test_destination", "connections": []},
#     )
#     result = await hass.config_entries.flow.async_init(
#         config_flow.DOMAIN, context={"source": "user"}
#     )

#     assert result["type"] == "form"
#     assert result["step_id"] == "user"
#     assert result["handler"] == "swiss_public_transport"
#     assert result["data_schema"] == config_flow.DATA_SCHEMA


async def test_flow_user_init_data_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test success response."""
    aioclient_mock.get(
        "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
        json={
            "from": {"id": 1, "name": "test_start"},
            "to": {"id": 2, "name": "test_destination"},
            "connections": [],
        },
    )
    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
        user_input={
            CONF_START: "test_start",
            CONF_DESTINATION: "test_destination",
        },
    )

    assert result["type"] == "create_entry"
    assert (
        result["result"].title == "swiss_public_transport_test_start_test_destination"
    )

    assert {
        CONF_START: "test_start",
        CONF_DESTINATION: "test_destination",
    } == result["data"]


async def test_flow_user_init_data_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test client errors."""
    aioclient_mock.get(
        "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
        json={
            "from": {"id": 1, "name": "test_start"},
            "to": {"id": 2, "name": "test_destination"},
            "connections": [],
        },
        exc=aiohttp.ClientError,
    )
    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
        user_input={
            CONF_START: "test_start",
            CONF_DESTINATION: "test_destination",
        },
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "client"


async def test_flow_user_init_data_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test unknown errors."""
    aioclient_mock.get(
        "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
        json={
            "from": {"id": 1, "name": "test_start"},
            "to": {"id": 2, "name": "test_destination"},
            # Missing connections
            # "connections": [],
        },
    )
    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
        user_input={
            CONF_START: "test_start",
            CONF_DESTINATION: "test_destination",
        },
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


MOCK_DATA = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}


async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test import flow."""
    aioclient_mock.get(
        "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
        json={
            "from": {"id": 1, "name": "test_start"},
            "to": {"id": 2, "name": "test_destination"},
            "connections": [],
        },
    )
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["result"].unique_id
        == "swiss_public_transport_test_start_test_destination"
    )
    assert result["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_client_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test import flow."""
    aioclient_mock.get(
        "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
        json={
            "from": {"id": 1, "name": "test_start"},
            "to": {"id": 2, "name": "test_destination"},
            "connections": [],
        },
        exc=aiohttp.ClientError,
    )
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "client"


async def test_import_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test import flow."""
    aioclient_mock.get(
        "http://transport.opendata.ch/v1/connections?from=test_start&to=test_destination",
        json={
            "from": {"id": 1, "name": "test_start"},
            "to": {"id": 2, "name": "test_destination"},
            # Missing connections
            # "connections": [],
        },
    )
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test we abort import when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        unique_id="swiss_public_transport_test_start_test_destination",
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
