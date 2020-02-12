"""Test Dynalite config flow."""
from unittest.mock import call, patch

from homeassistant.components.dynalite import config_flow


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
