"""Test Slack config flow."""

import json
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.slack.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    AUTH_URL,
    CONF_DATA,
    CONF_INPUT,
    TEAM_ID,
    TEAM_NAME,
    create_entry,
    mock_connection,
)

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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEAM_NAME
    assert result["data"] == CONF_DATA
    assert result["result"].unique_id == TEAM_ID


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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow with invalid token."""
    mock_connection(aioclient_mock, "invalid_auth")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow with unreachable server."""
    mock_connection(aioclient_mock, "cannot_connect")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test user initialized flow with unreachable server."""
    with patch(
        "homeassistant.components.slack.config_flow.AsyncWebClient.auth_test"
    ) as mock:
        mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONF_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow updates the API key."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == CONF_DATA | {CONF_API_KEY: "new_token"}


@pytest.mark.parametrize("error", ["invalid_auth", "cannot_connect"])
async def test_flow_reauth_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error: str
) -> None:
    """Test reauth flow handles errors and can recover."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)

    mock_connection(aioclient_mock, error)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new_token"


async def test_flow_reauth_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow handles unexpected errors and can recover."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.slack.config_flow.AsyncWebClient.auth_test",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "new_token"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_flow_reauth_wrong_account(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow aborts when the API key belongs to another workspace."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)

    aioclient_mock.post(
        AUTH_URL,
        text=json.dumps(
            {
                "ok": True,
                "url": "https://other.slack.com/",
                "team": "Other Team",
                "team_id": "OTHER123",
                "user_id": "ABCDEF12345",
            }
        ),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "other_token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data == CONF_DATA
