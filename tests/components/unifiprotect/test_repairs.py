"""Test repairs for unifiprotect."""
from __future__ import annotations

from copy import copy
from http import HTTPStatus
from unittest.mock import Mock

from pyunifiprotect.data import Camera, Version

from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import MockUFPFixture, init_entry

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_ea_warning_ignore(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""

    version = ufp.api.bootstrap.nvr.version
    assert version.is_prerelease
    await init_entry(hass, ufp, [])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "ea_warning":
            issue = i
    assert issue is not None

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "ea_warning"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"version": str(version)}
    assert data["step_id"] == "start"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"version": str(version)}
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"


async def test_ea_warning_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test EA warning is created if using prerelease version of Protect."""

    version = ufp.api.bootstrap.nvr.version
    assert version.is_prerelease
    await init_entry(hass, ufp, [])
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "ea_warning":
            issue = i
    assert issue is not None

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "ea_warning"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"version": str(version)}
    assert data["step_id"] == "start"

    new_nvr = copy(ufp.api.bootstrap.nvr)
    new_nvr.version = Version("2.2.6")
    mock_msg = Mock()
    mock_msg.changed_data = {"version": "2.2.6"}
    mock_msg.new_obj = new_nvr

    ufp.api.bootstrap.nvr = new_nvr
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"


async def test_deprecate_smart_default(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate Sensor repair does not exist by default (new installs)."""

    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_smart_sensor":
            issue = i
    assert issue is None


async def test_deprecate_smart_no_automations(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate Sensor repair exists for existing installs."""

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{doorbell.mac}_detected_object",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_smart_sensor":
            issue = i
    assert issue is None
