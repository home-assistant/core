"""Tests for the Advantage Air component."""

from aiohttp import web

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry, load_fixture

payload_without_sensor = load_fixture("advantage_air/payload_without_sensor.json")
payload_with_sensor = load_fixture("advantage_air/payload_with_sensor.json")


async def api_response_without_sensor(request):
    """Advantage Air API response."""
    return web.Response(body=payload_without_sensor)


async def api_response_with_sensor(request):
    """Advantage Air API response."""
    return web.Response(body=payload_with_sensor)


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
