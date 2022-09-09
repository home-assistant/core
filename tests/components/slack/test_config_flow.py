"""Test Slack config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.slack.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import CONF_DATA, CONF_INPUT, TEAM_NAME, create_entry, mock_connection

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_flow_user(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow."""
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEAM_NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow with duplicate server."""
    create_entry(hass)
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow with invalid token."""
    mock_connection(aioclient_mock, "invalid_auth")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONF_DATA,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow with unreachable server."""
    mock_connection(aioclient_mock, "cannot_connect")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONF_DATA,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with patch(
        "homeassistant.components.slack.config_flow.WebClient.auth_test"
    ) as mock:
        mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_flow_import(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an import flow."""
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=CONF_DATA,
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEAM_NAME
    assert result["data"] == CONF_DATA


async def test_flow_import_no_name(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test import flow with no name in config."""
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=CONF_INPUT,
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == TEAM_NAME
    assert result["data"] == CONF_DATA


async def test_flow_import_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an import flow already configured."""
    create_entry(hass)
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=CONF_DATA,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
