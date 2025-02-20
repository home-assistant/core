"""Test the Remote Calendar config flow."""

from unittest.mock import AsyncMock

import httpx
from httpx import ConnectError, HTTPStatusError, UnsupportedProtocol
import pytest

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CALENDAR_NAME, CALENDER_URL


async def test_form_import_ics(
    hass: HomeAssistant, mock_httpx_client: AsyncMock
) -> None:
    """Test we get the import form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "exception_factory",
    [
        lambda *args, **kwargs: ValueError("Test error"),
        lambda *args, **kwargs: ConnectError("Test error"),
        lambda *args, **kwargs: HTTPStatusError(
            "Test error",
            request=httpx.Request("GET", "http://example.com"),
            response=httpx.Response(
                400, request=httpx.Request("GET", "http://example.com")
            ),
        ),
        lambda *args, **kwargs: UnsupportedProtocol("Test error"),
    ],
)
async def test_form_inavild_url(
    hass: HomeAssistant, mock_httpx_client: AsyncMock, exception_factory
) -> None:
    """Test we get the import form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    mock_httpx_client.get.side_effect = exception_factory()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: "invalid",
        },
    )
    assert result2["type"] is FlowResultType.FORM


async def test_no_valid_calendar(
    hass: HomeAssistant, mock_httpx_client: AsyncMock
) -> None:
    """Test, dass bei ungültigem ICS-Content das Import-Formular erneut angezeigt wird."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    setattr(mock_httpx_client.get.return_value, "text", "invalid ICS content")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )

    assert result2["type"] is FlowResultType.FORM
