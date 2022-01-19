"""Test the Z-Wave JS diagnostics."""
from unittest.mock import patch

from homeassistant.components.zwave_js.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_config_entry_diagnostics(hass, integration):
    """Test the config entry level diagnostics data dump."""
    with patch(
        "homeassistant.components.zwave_js.diagnostics.dump_msgs",
        return_value=[{"hello": "world"}, {"second": "msg"}],
    ):
        result = await async_get_config_entry_diagnostics(hass, integration)
        assert result == [{"hello": "world"}, {"second": "msg"}]
