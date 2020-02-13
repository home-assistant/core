"""Test Dynalite config flow."""
from unittest.mock import Mock, call, patch

from homeassistant.components.dynalite import config_flow


async def test_configured_hosts():
    """Test the configured_host method."""
    hass = Mock()
    entry = Mock()
    host = "abc"
    entry.data = {"host": host}
    hass.config_entries.async_entries = Mock(return_value=[entry])
    assert config_flow.configured_hosts(hass) == {host}


async def test_step_import():
    """Test a successful setup."""
    flow_handler = config_flow.DynaliteFlowHandler()
    with patch.object(flow_handler, "context", create=True):
        with patch.object(flow_handler, "hass", create=True):
            with patch.object(
                flow_handler, "async_create_entry", create=True
            ) as mock_create:
                host = "1.2.3.4"
                await flow_handler.async_step_import({"host": host})
                mock_create.assert_called_once()
                assert mock_create.mock_calls[0] == call(
                    title=host, data={"host": host}
                )
