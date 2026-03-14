"""Tests for Cielo config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from cieloconnectapi.exceptions import AuthenticationError
import pytest

from homeassistant.components.cielo_home.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_TOKEN = "valid-test-token"
MOCK_CIELO_CLIENT_CTOR = "homeassistant.components.cielo_home.config_flow.CieloClient"


def _devices_payload(parsed: dict | None) -> MagicMock:
    """Return a mock object shaped like cieloconnectapi get_devices_data() result."""
    payload = MagicMock()
    payload.raw = {}
    payload.parsed = parsed
    return payload


async def test_full_config_flow_success(hass: HomeAssistant) -> None:
    """Test successful config flow with valid API key."""
    mock_client = MagicMock()
    mock_client.username = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "  test-api-key  "},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Cielo Home"
    assert result2["data"][CONF_API_KEY] == "test-api-key"
    assert result2["data"][CONF_TOKEN] == MOCK_TOKEN


async def test_full_config_flow_abort_already_configured(hass: HomeAssistant) -> None:
    """Test the flow aborts when the account is already configured."""
    mock_client = MagicMock()
    mock_client.username = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY

        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result3["type"] is FlowResultType.FORM

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("api_error", "flow_error_key"),
    [
        (ConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_error_mapping(
    hass: HomeAssistant, api_error: type[Exception], flow_error_key: str
) -> None:
    """Test we handle various API errors correctly.

    These errors may occur from either token retrieval or device fetch
    (your flow does both in validation).
    """
    mock_client = MagicMock()
    mock_client.username = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)
    mock_client.get_devices_data = AsyncMock(side_effect=api_error)

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == flow_error_key


async def test_form_error_mapping_invalid_auth(hass: HomeAssistant) -> None:
    """Test AuthenticationError maps to invalid_auth."""

    mock_client = MagicMock()
    mock_client.username = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(side_effect=AuthenticationError)
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"
