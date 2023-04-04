"""Tests for the Atag config flow."""
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.atag import DOMAIN
from homeassistant.core import HomeAssistant

from . import UID, USER_INPUT, init_integration, mock_connection

from tests.test_util.aiohttp import AiohttpClientMocker

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the form is served with no input."""
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_adding_second_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that only one Atag configuration is allowed."""
    entry = await init_integration(hass, aioclient_mock)
    entry.unique_id = UID

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    with patch(
        "pyatag.AtagOne.id",
        new_callable=PropertyMock(return_value="secondary_device"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on Atag connection error."""
    mock_connection(aioclient_mock, conn_error=True)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=USER_INPUT,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unauthorized(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show correct form when Unauthorized error is raised."""
    mock_connection(aioclient_mock, authorized=False)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unauthorized"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == UID
    assert result["result"].unique_id == UID
