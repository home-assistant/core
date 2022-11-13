"""Test repairs for unifiprotect."""

from __future__ import annotations

from copy import copy
from http import HTTPStatus
from unittest.mock import ANY, Mock

from pyunifiprotect.data import Version

from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry


async def test_ea_warning_ignore(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client,
    hass_ws_client,
):
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
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == "ea_warning"

    url = "/api/repairs/issues/fix"
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "ea_warning"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": {"version": str(version)},
        "errors": None,
        "flow_id": ANY,
        "handler": DOMAIN,
        "last_step": None,
        "step_id": "start",
        "type": "form",
    }

    url = f"/api/repairs/issues/fix/{flow_id}"
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": {"version": str(version)},
        "errors": None,
        "flow_id": ANY,
        "handler": DOMAIN,
        "last_step": None,
        "step_id": "confirm",
        "type": "form",
    }

    url = f"/api/repairs/issues/fix/{flow_id}"
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "description": None,
        "description_placeholders": None,
        "flow_id": ANY,
        "handler": DOMAIN,
        "title": "",
        "type": "create_entry",
        "version": 1,
    }


async def test_ea_warning_fix(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_client,
    hass_ws_client,
):
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
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == "ea_warning"

    url = "/api/repairs/issues/fix"
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "ea_warning"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": {"version": str(version)},
        "errors": None,
        "flow_id": ANY,
        "handler": DOMAIN,
        "last_step": None,
        "step_id": "start",
        "type": "form",
    }

    new_nvr = copy(ufp.api.bootstrap.nvr)
    new_nvr.version = Version("2.2.6")
    mock_msg = Mock()
    mock_msg.changed_data = {"version": "2.2.6"}
    mock_msg.new_obj = new_nvr

    ufp.api.bootstrap.nvr = new_nvr
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    url = f"/api/repairs/issues/fix/{flow_id}"
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "description": None,
        "description_placeholders": None,
        "flow_id": ANY,
        "handler": DOMAIN,
        "title": "",
        "type": "create_entry",
        "version": 1,
    }
