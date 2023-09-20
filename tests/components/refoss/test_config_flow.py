"""Tests for the Refoss config flow."""
from __future__ import annotations

from unittest.mock import Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.refoss.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_configured(hass: HomeAssistant):
    """Test a successful config flow."""

    with patch(
        "homeassistant.components.refoss.config_flow._get_unique_id",
        return_value="refoss_30.6598628_104.0633717",
    ), patch("socket.socket", return_value=Mock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_already_configured_abort(hass: HomeAssistant) -> None:
    """test_already_configured_abort."""

    with patch(
        "homeassistant.components.refoss.config_flow._get_unique_id",
        return_value="refoss_30.6598628_104.0633717",
    ) as mock_unique_id:
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=mock_unique_id.return_value,
        )
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"
