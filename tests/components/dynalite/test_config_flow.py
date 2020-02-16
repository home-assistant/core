"""Test Dynalite config flow."""
from unittest.mock import Mock, call, patch

from homeassistant.components.dynalite import config_flow

from tests.common import mock_coro


async def test_step_import():
    """Test a successful setup."""
    flow_handler = config_flow.DynaliteFlowHandler()
    with patch.object(flow_handler, "context", create=True):
        with patch.object(flow_handler, "hass", create=True) as mock_hass:
            with patch.object(
                flow_handler, "async_create_entry", create=True
            ) as mock_create:
                host = "1.2.3.4"
                entry1 = Mock()
                entry1.data = {"host": host}
                entry2 = Mock()
                entry2.data = {"host": "5.5"}
                mock_hass.config_entries.async_entries = Mock(
                    return_value=[entry1, entry2]
                )
                mock_hass.config_entries.async_remove = Mock(
                    return_value=mock_coro(Mock())
                )
                await flow_handler.async_step_import({"host": "1.2.3.4"})
                mock_hass.config_entries.async_remove.assert_called_once()
                assert mock_hass.config_entries.async_remove.mock_calls[0] == call(
                    entry1.entry_id
                )
                mock_create.assert_called_once()
                assert mock_create.mock_calls[0] == call(
                    title=host, data={"host": host}
                )
