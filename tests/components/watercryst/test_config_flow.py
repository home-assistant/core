"""Test the WATERCryst BIOCAT config flow."""

from unittest.mock import AsyncMock

from httpx import HTTPStatusError, Request, RequestError, Response
from pyocat import WTCApiDisabledError, WTCApiTemporaryError, WTCApiUnauthorizedError
import pytest

from homeassistant import config_entries
from homeassistant.components.watercryst.const import CONF_BSN, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
            CONF_BSN: "2026123456789123",
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Device"
    assert result["data"] == {
        CONF_BSN: "2026123456789123",
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
            CONF_BSN: "2026123456789123",
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _http_status_error(status_code: int) -> HTTPStatusError:
    """Create an HTTP status error."""
    request = Request("GET", "https://example.com/v1/device")
    response = Response(status_code, request=request)
    return HTTPStatusError(
        "Unexpected HTTP status",
        request=request,
        response=response,
    )


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WTCApiUnauthorizedError(), "invalid_auth"),
        (WTCApiDisabledError(), "api_disabled"),
        (WTCApiTemporaryError(), "cannot_connect"),
        (_http_status_error(404), "cannot_connect"),
        (
            RequestError(
                message="",
                request=Request("GET", "https://example.com/v1/device"),
            ),
            "cannot_connect",
        ),
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
            CONF_BSN: "2026123456789123",
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api_client.get_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2026123456789123",
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Device"
    assert result["data"] == {
        CONF_BSN: "2026123456789123",
        CONF_API_KEY: "<api-key>",
    }

    mock_setup_entry.assert_awaited_once()
    mock_api_client.get_state.assert_not_awaited()


@pytest.mark.usefixtures("mock_api_client")
async def test_form_wrong_device_serial(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test an incorrect BIOCAT serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BSN: "2026123456789124",
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_device_serial"}
    mock_setup_entry.assert_not_awaited()
