"""Test the WATERCryst BIOCAT config flow."""

from unittest.mock import AsyncMock

from pyocat import WTCApiDisabledError, WTCApiTemporaryError, WTCApiUnauthorizedError
import pytest

from homeassistant import config_entries
from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import http_status_error, request_error

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_api_client")
async def test_form_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Device"
    assert result["data"] == {
        CONF_API_KEY: "<api-key>",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_api_client")
async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate entry handling."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="2026123456789123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WTCApiUnauthorizedError(), "invalid_auth"),
        (WTCApiDisabledError(), "api_disabled"),
        (WTCApiTemporaryError(), "cannot_connect"),
        (http_status_error(404), "cannot_connect"),
        (request_error(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_form_raise_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test config flow error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_api_client.get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api_client.get_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Device"
    assert result["data"] == {
        CONF_API_KEY: "<api-key>",
    }

    mock_setup_entry.assert_awaited_once()
    mock_api_client.get_state.assert_not_awaited()
