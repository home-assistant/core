"""Test the Google Translate Text-to-Speech repairs flow."""
from http import HTTPStatus
from unittest.mock import AsyncMock

from homeassistant.components.google_translate.const import CONF_TLD, DOMAIN
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.components.tts import CONF_LANG
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_deprecation_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the deprecation repair flow."""
    LANG = "de"
    TLD = "de"
    config = {
        CONF_PLATFORM: DOMAIN,
        CONF_LANG: LANG,
        CONF_TLD: TLD,
    }
    issue_id = f"{LANG}_{TLD}"
    await async_setup_component(hass, "tts", {"tts": config})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})

    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0

    issue = next(
        (i for i in msg["result"]["issues"] if i["domain"] == "google_translate"), None
    )

    assert issue is not None
    assert issue["issue_id"] == issue_id
    assert issue["is_fixable"]
    url = RepairsFlowIndexView.url
    resp = await client.post(
        url, json={"handler": DOMAIN, "issue_id": issue["issue_id"]}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Apply fix
    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"

    # Assert the issue is resolved
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0


async def test_repair_flow_where_entry_already_exists(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the deprecation repair flow and an entry already exists."""
    LANG = "de"
    TLD = "de"
    config = {
        CONF_PLATFORM: DOMAIN,
        CONF_LANG: LANG,
        CONF_TLD: TLD,
    }
    issue_id = f"{LANG}_{TLD}"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LANG: LANG,
            CONF_TLD: TLD,
        },
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, "tts", {"tts": config})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})

    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = next(
        (i for i in msg["result"]["issues"] if i["domain"] == "google_translate"), None
    )
    assert issue is not None
    assert issue["issue_id"] == issue_id
    assert issue["is_fixable"]
    assert issue["translation_key"] == "migration"

    url = RepairsFlowIndexView.url
    resp = await client.post(
        url, json={"handler": DOMAIN, "issue_id": issue["issue_id"]}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "abort"
    assert data["reason"] == "already_configured"

    # We should now have a non_fixable issue left since there is still
    # a config in configuration.yaml
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = next(
        (i for i in msg["result"]["issues"] if i["domain"] == "google_translate"), None
    )
    assert issue is not None
    assert issue["issue_id"] == issue_id
    assert not issue["is_fixable"]
    assert issue["translation_key"] == "deprecated_yaml"
