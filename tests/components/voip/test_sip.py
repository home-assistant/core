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

    with pytest.raises(OSError), socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM
    ) as sock:
        # Server should have the port
        sock.bind(("127.0.0.1", 5060))

    # Configure different port
    result = await hass.config_entries.options.async_init(
        entry.entry_id,
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"sip_port": 5061},
    )
    await hass.async_block_till_done()

    # Server should be stopped now on 5060
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 5060))

    with pytest.raises(OSError), socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM
    ) as sock:
        # Server should now have the new port
        sock.bind(("127.0.0.1", 5061))

    # Shut down
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # Server should be stopped
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 5061))
