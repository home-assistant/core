"""Test SIP server."""
import socket

import pytest

from homeassistant import config_entries
from homeassistant.components import voip
from homeassistant.core import HomeAssistant


async def test_create_sip_server(hass: HomeAssistant, socket_enabled) -> None:
    """Tests starting/stopping SIP server."""
    result = await hass.config_entries.flow.async_init(
        voip.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    entry = result["result"]
    await hass.async_block_till_done()

    with pytest.raises(OSError):
        # Server should have the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 5060))

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # Server should be stopped
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5060))
    sock.close()
