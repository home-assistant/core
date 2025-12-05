"""Tests for Lytiva config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    
    # Mock successful connection
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        # Simulate successful connection callback
        def mock_connect(broker, port, keepalive):
            # Trigger on_connect callback with success
            return 0
        
        mock_mqtt_client.connect.side_effect = mock_connect
        
        with patch(
            "homeassistant.components.lytiva.config_flow.LytivaConfigFlow._test_connection",
            return_value="success",
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "broker": "192.168.1.100",
                    CONF_PORT: 1883,
                    CONF_USERNAME: "test_user",
                    CONF_PASSWORD: "test_pass",
                },
            )
    
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Lytiva (192.168.1.100)"
    assert result2["data"] == {
        "broker": "192.168.1.100",
        CONF_PORT: 1883,
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test user flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    with patch(
        "homeassistant.components.lytiva.config_flow.LytivaConfigFlow._test_connection",
        return_value="cannot_connect",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                CONF_PORT: 1883,
            },
        )
    
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test user flow with authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    with patch(
        "homeassistant.components.lytiva.config_flow.LytivaConfigFlow._test_connection",
        return_value="auth_error",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                CONF_PORT: 1883,
                CONF_USERNAME: "wrong_user",
                CONF_PASSWORD: "wrong_pass",
            },
        )
    
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when integration is already configured."""
    mock_config_entry.add_to_hass(hass)
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    with patch(
        "homeassistant.components.lytiva.config_flow.LytivaConfigFlow._test_connection",
        return_value="success",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                CONF_PORT: 1883,
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
        )
    
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_connection_test_exception(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test connection test with exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    mock_mqtt_client.connect.side_effect = Exception("Connection error")
    
    with patch(
        "homeassistant.components.lytiva.config_flow.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "broker": "192.168.1.100",
                CONF_PORT: 1883,
            },
        )
    
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_with_default_port(hass: HomeAssistant) -> None:
    """Test form displays with default port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    
    # Check that default port is 1883
    schema = result["data_schema"].schema
    port_field = None
    for key in schema:
        if hasattr(key, "default") and str(key) == "port":
            port_field = key
            break
    
    assert port_field is not None
    assert port_field.default() == 1883
