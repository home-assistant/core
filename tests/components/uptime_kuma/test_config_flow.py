"""Test the Uptime Kuma config flow."""

from unittest.mock import AsyncMock

import pytest
from pyuptimekuma import (
    UptimeKumaAuthenticationException,
    UptimeKumaConnectionException,
)

from homeassistant.components.uptime_kuma.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pyuptimekuma")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "uptime.example.org"
    assert result["data"] == {
        CONF_URL: "https://uptime.example.org/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: "apikey",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (UptimeKumaConnectionException, "cannot_connect"),
        (UptimeKumaAuthenticationException, "invalid_auth"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyuptimekuma: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test we handle errors and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pyuptimekuma.async_get_monitors.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_pyuptimekuma.async_get_monitors.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "uptime.example.org"
    assert result["data"] == {
        CONF_URL: "https://uptime.example.org/",
        CONF_VERIFY_SSL: True,
        CONF_API_KEY: "apikey",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pyuptimekuma")
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://uptime.example.org",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
