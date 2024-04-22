"""Test repairs for System Monitor."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import Mock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.components.systemmonitor.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import ANY, MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_migrate_process_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test migrating process sensor to binary sensor."""
    mock_config_entry = MockConfigEntry(
        title="System Monitor",
        domain=DOMAIN,
        data={},
        options={
            "binary_sensor": {"process": ["python3", "pip"]},
            "sensor": {"process": ["python3", "pip"]},
            "resources": [
                "disk_use_percent_/",
                "disk_use_percent_/home/notexist/",
                "memory_free_",
                "network_out_eth0",
                "process_python3",
            ],
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN) == snapshot(
        name="before_migration"
    )

    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()

    entity = "sensor.system_monitor_process_python3"
    state = hass.states.get(entity)
    assert state

    assert entity_registry.async_get(entity)

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "process_sensor":
            issue = i
    assert issue is not None

    url = RepairsFlowIndexView.url
    resp = await client.post(
        url, json={"handler": DOMAIN, "issue_id": "process_sensor"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "migrate_process_sensor"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url, json={})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    # Cannot use identity `is` check here as the value is parsed from JSON
    assert data["type"] == FlowResultType.CREATE_ENTRY.value
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.system_monitor_process_python3")
    assert state

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "migrate_process_sensor":
            issue = i
    assert not issue

    entity = "sensor.system_monitor_process_python3"
    state = hass.states.get(entity)
    assert not state

    assert not entity_registry.async_get(entity)

    assert hass.config_entries.async_entries(DOMAIN) == snapshot(name="after_migration")


async def test_other_fixable_issues(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry_enabled_by_default: None,
    mock_added_config_entry: ConfigEntry,
) -> None:
    """Test fixing other issues."""
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    issue = {
        "breaks_in_ha_version": "2022.9.0dev0",
        "domain": DOMAIN,
        "issue_id": "issue_1",
        "is_fixable": True,
        "learn_more_url": "",
        "severity": "error",
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
        "breaks_in_ha_version": "2022.9.0dev0",
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
