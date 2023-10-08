"""Tests for the refoss Integration."""
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.refoss.const import DOMAIN
from homeassistant.core import HomeAssistant


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_has_no_devices(hass: HomeAssistant) -> None:
    """Test setting up Refoss no devices."""
    with patch(
        "homeassistant.components.refoss.config_flow.refoss_discovery_server",
        return_value=AsyncMock(),
    ) as mock_discovery:
        mock_discovery.broadcast_msg = AsyncMock
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
