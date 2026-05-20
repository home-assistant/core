"""Tests for Renson WAVES config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.renson_waves.client import RensonWavesCannotConnect
from homeassistant.components.renson_waves.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_user_step_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user step with successful probe."""
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

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "WAVES Living Room"
        assert result["data"] == {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.asyncio
async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step when device is unreachable."""
    with patch(
        "homeassistant.components.renson_waves.config_flow.RensonWavesClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.async_get_constellation.side_effect = RensonWavesCannotConnect(
            "Cannot connect"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_confirm_step(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test confirm step creates entry."""
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

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "WAVES Living Room"
        assert result["data"] == {CONF_HOST: "192.168.1.100", CONF_PORT: 8000}
        assert len(mock_setup_entry.mock_calls) == 1
