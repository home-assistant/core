"""Tests for the Refoss config flow."""
from __future__ import annotations

from unittest.mock import Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.refoss.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_async_step_user_socket_fail(hass: HomeAssistant):
    """Test a  config flow."""

    with patch("socket.socket", return_value=Mock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "socket_start_fail"
