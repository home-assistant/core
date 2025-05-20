"""Test the Axion DMX config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.axion_dmx.config_flow import (
    AxionDmxAuthError,
    AxionDmxConnectionError,
)
from homeassistant.components.axion_dmx.const import (
    CONF_CHANNEL,
    CONF_LIGHT_TYPE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "rgb",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Axion DMX Light - Channel 1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_CHANNEL: 1,
        CONF_LIGHT_TYPE: "rgb",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (AxionDmxAuthError, "invalid_auth"),
        (AxionDmxConnectionError, "cannot_connect"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test config flow handles auth and connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.axion_dmx.config_flow.AxionDmxApi.authenticate",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "rgb",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    with (
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi.authenticate",
            return_value=True,
        ),
        patch(
            "homeassistant.components.axion_dmx.AxionDmxApi._send_tcp_command",
            return_value="OK",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "rgbw",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Axion DMX Light - Channel 1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_CHANNEL: 1,
        CONF_LIGHT_TYPE: "rgbw",
    }
    assert len(mock_setup_entry.mock_calls) == 1
