"""Test the LM Studio config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from homeassistant import config_entries
from homeassistant.components.lmstudio.config_flow import validate_input
from homeassistant.components.lmstudio.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "http://localhost:1234/v1"
    assert result2["data"] == {
        "base_url": "http://localhost:1234/v1",
        "api_key": "test-key",
    }
    assert len(result2["subentries"]) == 2
    assert result2["subentries"][0]["subentry_type"] == "conversation"
    assert result2["subentries"][1]["subentry_type"] == "ai_task_data"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow.validate_input",
        side_effect=openai.AuthenticationError(
            response=httpx.Response(
                status_code=401, request=httpx.Request(method="GET", url="test")
            ),
            body=None,
            message="Invalid API key",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow.validate_input",
        side_effect=openai.APIConnectionError(
            request=httpx.Request(method="GET", url="test")
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lmstudio.config_flow.validate_input",
        side_effect=Exception("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test we handle already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"base_url": "http://localhost:1234/v1", "api_key": "test-key"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_validate_input_success(
    hass: HomeAssistant, mock_openai_client_config_flow: AsyncMock
) -> None:
    """Test validate_input function success."""
    await validate_input(
        hass,
        {
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        },
    )

    mock_openai_client_config_flow.with_options.assert_called_once_with(timeout=10.0)
    mock_openai_client_config_flow.with_options.return_value.models.list.assert_called_once()


async def test_validate_input_connection_error(hass: HomeAssistant) -> None:
    """Test validate_input function with connection error."""
    with (
        patch(
            "homeassistant.components.lmstudio.config_flow.openai.AsyncOpenAI",
            side_effect=openai.APIConnectionError(
                request=httpx.Request(method="GET", url="test")
            ),
        ),
        pytest.raises(openai.APIConnectionError),
    ):
        await validate_input(
            hass,
            {
                "base_url": "http://localhost:1234/v1",
                "api_key": "test-key",
            },
        )
