"""Test the Homeassistant repairs module."""

from http import HTTPStatus

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_integration_not_found_confirm_step(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the integration_not_found issue confirm step."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "test1", {}) is False
    await hass.async_block_till_done()
    entry1 = MockConfigEntry(domain="test1")
    entry1.add_to_hass(hass)
    entry2 = MockConfigEntry(domain="test1")
    entry2.add_to_hass(hass)
    issue_id = "integration_not_found.test1"

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == issue_id
    assert issue["translation_placeholders"] == {"domain": "test1"}

    url = RepairsFlowIndexView.url
    resp = await http_client.post(url, json={"handler": DOMAIN, "issue_id": issue_id})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "init"
    assert data["description_placeholders"] == {"domain": "test1"}

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)

    # Show menu
    resp = await http_client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "menu"

    # Apply fix
    resp = await http_client.post(url, json={"next_step_id": "confirm"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"

    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(entry1.entry_id) is None
    assert hass.config_entries.async_get_entry(entry2.entry_id) is None

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


async def test_integration_not_found_ignore_step(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the integration_not_found issue ignore step."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "test1", {}) is False
    await hass.async_block_till_done()
    entry1 = MockConfigEntry(domain="test1")
    entry1.add_to_hass(hass)
    issue_id = "integration_not_found.test1"

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == issue_id
    assert issue["translation_placeholders"] == {"domain": "test1"}

    url = RepairsFlowIndexView.url
    resp = await http_client.post(url, json={"handler": DOMAIN, "issue_id": issue_id})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "init"
    assert data["description_placeholders"] == {"domain": "test1"}

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)

    # Show menu
    resp = await http_client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "menu"

    # Apply fix
    resp = await http_client.post(url, json={"next_step_id": "ignore"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "abort"
    assert data["reason"] == "issue_ignored"

    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(entry1.entry_id)

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    assert msg["result"]["issues"][0].get("dismissed_version") is not None
