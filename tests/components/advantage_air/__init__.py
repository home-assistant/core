"""Tests for the Advantage Air component."""

from aiohttp import web

from tests.common import load_fixture

payload_without_sensor = load_fixture("advantage_air/payload_without_sensor.json")
payload_with_sensor = load_fixture("advantage_air/payload_with_sensor.json")


async def api_response_without_sensor(request):
    """Advantage Air API response."""
    return web.Response(body=payload_without_sensor)


async def api_response_with_sensor(request):
    """Advantage Air API response."""
    return web.Response(body=payload_with_sensor)
