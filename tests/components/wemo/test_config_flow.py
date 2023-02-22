"""Tests for Wemo config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import patch


async def test_not_discovered(hass: HomeAssistant) -> None:
    """Test setting up with no devices discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch("homeassistant.components.wemo.config_flow.pywemo") as mock_pywemo:
        mock_pywemo.discover_devices.return_value = []
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
