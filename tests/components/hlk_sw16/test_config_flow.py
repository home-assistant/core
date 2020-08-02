"""Test the Hi-Link HLK-SW16 config flow."""
import asyncio
import socket

from homeassistant import config_entries, setup
from homeassistant.components.hlk_sw16.const import DOMAIN

hlk_sw16_test_config = {
    "host": "1.1.1.1",
    "port": 8080,
}


def free_port():
    """Determine a free port using sockets."""
    free_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    free_socket.bind(("127.0.0.1", 0))
    free_socket.listen(5)
    port = free_socket.getsockname()[1]
    free_socket.close()
    return port


async def handle_hlk_sw16_status_read(reader, writer):
    """Echo a good status read back."""
    await reader.read(20)

    status_packet = b"\xcc\x0c\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x1b\xdd"

    writer.write(status_packet)
    await writer.drain()

    writer.close()


async def handle_hlk_sw16_bad_checksum(reader, writer):
    """Echo a status read with a bad checksum back."""
    await reader.read(20)

    status_packet = b"\xcc\x0c\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x1a\xdd"

    writer.write(status_packet)
    await writer.drain()

    writer.close()


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    port = free_port()

    server = await asyncio.start_server(handle_hlk_sw16_status_read, "127.0.0.1", port)

    await server.start_serving()

    conf = {
        "host": "127.0.0.1",
        "port": port,
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], conf,)

    assert result2["type"] == "create_entry"
    assert result2["title"] == "127.0.0.1:" + str(port)
    assert result2["data"] == {
        "host": "127.0.0.1",
        "port": port,
    }

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result3["type"] == "form"
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(result3["flow_id"], conf,)

    assert result4["type"] == "form"
    assert result4["errors"] == {"base": "already_configured"}
    await hass.async_block_till_done()
    server.close()


async def test_form_invalid_data(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    port = free_port()

    server = await asyncio.start_server(handle_hlk_sw16_bad_checksum, "127.0.0.1", port)

    await server.start_serving()

    conf = {
        "host": "127.0.0.1",
        "port": port,
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], conf,)

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
    server.close()


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    port = free_port()

    conf = {
        "host": "127.0.0.1",
        "port": port,
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], conf,)

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
