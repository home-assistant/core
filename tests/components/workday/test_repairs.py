"""Test repairs for unifiprotect."""
from __future__ import annotations

from http import HTTPStatus

from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.components.workday.const import DOMAIN
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    TEST_CONFIG_INCORRECT_COUNTRY,
    TEST_CONFIG_INCORRECT_PROVINCE,
    init_integration,
)

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_bad_country(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad country."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_COUNTRY)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert issue is not None

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "bad_country"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": entry.title}
    assert data["step_id"] == "country"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url, json={"country": "DE"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url, json={"province": "HB"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_country":
            issue = i
    assert not issue


async def test_bad_province(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test fixing bad province."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await init_integration(hass, TEST_CONFIG_INCORRECT_PROVINCE)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_province":
            issue = i
    assert issue is not None

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "bad_province"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {
        CONF_COUNTRY: "DE",
        "title": entry.title,
    }
    assert data["step_id"] == "province"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url, json={"province": "BW"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "bad_province":
            issue = i
    assert not issue
