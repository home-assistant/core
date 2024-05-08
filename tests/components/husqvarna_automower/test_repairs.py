"""Test repairs for Husqvarna Automower."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_cloud_user_fix(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_wrong_scope_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""
    await async_setup_component(hass, "repairs", {})
    await setup_integration(hass, mock_wrong_scope_config_entry)
    await async_process_repairs_platforms(hass)

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "wrong_scope":
            issue = i
    assert issue is not None

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "wrong_scope"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()
