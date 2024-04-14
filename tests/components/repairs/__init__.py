"""Tests for the repairs integration."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def get_repairs(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
):
    """Return the repairs list of issues."""
    assert await async_setup_component(hass, "repairs", {})

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await client.receive_json()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"]

    return msg["result"]["issues"]
