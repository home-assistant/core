"""Tests for the Advantage Air component."""

from aiohttp import web

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry, load_fixture

TEST_SYSTEM_DATA = load_fixture("advantage_air/getSystemData.json")
TEST_SET_RESPONSE = load_fixture("advantage_air/setAircon.json")


async def api_response(request):
    """Advantage Air API response."""
    if request.method == "GET":
        if request.path == "/getSystemData":
            return web.Response(body=TEST_SYSTEM_DATA)
        if request.path == "/setAircon":
            return web.Response(body=TEST_SET_RESPONSE)
    raise web.HTTPException


async def add_mock_config(hass, port):
    """Create a fake Advantage Air Config Entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test entry",
        unique_id="0123456",
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: port,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
