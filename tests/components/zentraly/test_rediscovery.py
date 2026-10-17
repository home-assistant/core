"""Test rediscovery through real entry unload and setup."""

from unittest.mock import MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST, PORT
from .test_config_flow import NEW_HOST, NEW_PORT, _zeroconf_info

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("host", "port", "setup_count", "disconnect_count"),
    [
        pytest.param(NEW_HOST, PORT, 2, 1, id="new-host"),
        pytest.param(HOST, NEW_PORT, 2, 1, id="new-port"),
        pytest.param(HOST, PORT, 1, 0, id="unchanged"),
    ],
)
async def test_loaded_entry_rediscovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_class: MagicMock,
    mock_api: MagicMock,
    host: str,
    port: int,
    setup_count: int,
    disconnect_count: int,
) -> None:
    """Network changes reconnect using the new endpoint; unchanged discovery does not."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_info(host=host, port=port),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.state is config_entries.ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_HOST] == host
    assert mock_config_entry.data[CONF_PORT] == port
    assert mock_api_class.call_count == setup_count
    assert mock_api_class.call_args.kwargs["host"] == host
    assert mock_api_class.call_args.kwargs["port"] == port
    assert mock_api.async_connect.await_count == setup_count
    assert mock_api.async_disconnect.call_count == disconnect_count
