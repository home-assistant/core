"""Tests for Renson WAVES config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.renson_waves.config_flow import RensonWavesConfigFlow
from homeassistant.components.renson_waves.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult


@pytest.mark.asyncio
async def test_user_step_success(hass):
    """Test user step with successful probe."""
    flow = RensonWavesConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.renson_waves.config_flow.RensonWavesClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.async_get_constellation.return_value = {
            "global": {
                "serial": {"value": "WAVES-ABC123"},
                "device_name": {"value": "WAVES Living Room"},
            }
        }

        result = await flow.async_step_user(
            {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"


@pytest.mark.asyncio
async def test_user_step_cannot_connect(hass):
    """Test user step when device is unreachable."""
    flow = RensonWavesConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.renson_waves.config_flow.RensonWavesClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.async_get_constellation.side_effect = Exception("Cannot connect")

        result = await flow.async_step_user(
            {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_confirm_step(hass):
    """Test confirm step creates entry."""
    flow = RensonWavesConfigFlow()
    flow.hass = hass
    flow._device_name = "WAVES Living Room"
    flow.context = {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}

    result = await flow.async_step_confirm()

    assert result["type"] == "create_entry"
    assert result["title"] == "WAVES Living Room"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PORT] == 8000
