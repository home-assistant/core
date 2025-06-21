"""Tests for the repairs integration."""

from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient

from homeassistant.components.repairs.issue_handler import (  # noqa: F401
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
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


async def start_repair_fix_flow(
    client: TestClient, handler: str, issue_id: str
) -> dict[str, Any]:
    """Start a flow from an issue."""
    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": handler, "issue_id": issue_id})
    assert resp.status == HTTPStatus.OK, f"Error: {resp.status}, {await resp.text()}"
    return await resp.json()


async def process_repair_fix_flow(
    client: TestClient, flow_id: str, json: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the repairs list of issues."""
    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url, json=json)
    assert resp.status == HTTPStatus.OK, f"Error: {resp.status}, {await resp.text()}"
    return await resp.json()
