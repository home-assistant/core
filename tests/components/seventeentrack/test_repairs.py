"""Tests for the seventeentrack repair flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.components.seventeentrack import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.setup import async_setup_component

from . import goto_future, init_integration
from .conftest import DEFAULT_SUMMARY_LENGTH, get_package

from tests.common import ANY, MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_repair(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)  # 2
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH
    assert len(issue_registry.issues) == 1

    package = get_package()
    mock_seventeentrack.return_value.profile.packages.return_value = [package]
    await goto_future(hass, freezer)

    assert hass.states.get("sensor.17track_package_friendly_name_1")
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1

    assert "deprecated" not in mock_config_entry.data

    repair_issue = issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"deprecate_sensor_{mock_config_entry.entry_id}"
    )

    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})

    client = await hass_client()

    resp = await client.post(
        RepairsFlowIndexView.url,
        json={"handler": DOMAIN, "issue_id": repair_issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "step_id": "confirm",
        "data_schema": [],
        "errors": None,
        "description_placeholders": None,
        "last_step": None,
        "preview": None,
    }

    resp = await client.post(RepairsFlowIndexView.url + f"/{flow_id}")
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "handler": DOMAIN,
        "flow_id": flow_id,
        "description": None,
        "description_placeholders": None,
    }

    assert mock_config_entry.data["deprecated"]

    repair_issue = issue_registry.async_get_issue(
        domain=DOMAIN, issue_id="deprecate_sensor"
    )

    assert repair_issue is None

    await goto_future(hass, freezer)
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_other_fixable_issues(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fixing other issues."""

    await init_integration(hass, mock_config_entry)

    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    issue = {
        "breaks_in_ha_version": "2025.1.0",
        "domain": DOMAIN,
        "issue_id": "issue_1",
        "is_fixable": True,
        "learn_more_url": "",
        "severity": IssueSeverity.ERROR,
        "translation_key": "issue_1",
    }
    ir.async_create_issue(
        hass,
        issue["domain"],
        issue["issue_id"],
        breaks_in_ha_version=issue["breaks_in_ha_version"],
        is_fixable=issue["is_fixable"],
        is_persistent=False,
        learn_more_url=None,
        severity=issue["severity"],
        translation_key=issue["translation_key"],
    )

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    results = msg["result"]["issues"]
    assert {
        "breaks_in_ha_version": "2025.1.0",
        "created": ANY,
        "dismissed_version": None,
        "domain": DOMAIN,
        "is_fixable": True,
        "issue_domain": None,
        "issue_id": "issue_1",
        "learn_more_url": None,
        "severity": "error",
        "translation_key": "issue_1",
        "translation_placeholders": None,
        "ignored": False,
    } in results

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": "issue_1"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    # Cannot use identity `is` check here as the value is parsed from JSON
    assert data["type"] == FlowResultType.CREATE_ENTRY.value
    await hass.async_block_till_done()
