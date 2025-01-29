"""Test the backup repair flows."""

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock

from homeassistant.components.backup import DOMAIN, store
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .common import BackupAgentTest, setup_backup_platform

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_agents_not_loaded_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test desired flow of the fix flow for legacy subscription."""
    issue_id = "automatic_backup_agents_not_loaded_test.agent"
    ws_client = await hass_ws_client(hass)
    hass_storage.update(
        {
            "backup": {
                "data": {
                    "backups": [],
                    "config": {
                        "agents": {},
                        "create_backup": {
                            "agent_ids": ["test.agent"],
                            "include_addons": None,
                            "include_all_addons": False,
                            "include_database": False,
                            "include_folders": None,
                            "name": None,
                            "password": None,
                        },
                        "retention": {"copies": None, "days": None},
                        "last_attempted_automatic_backup": None,
                        "last_completed_automatic_backup": None,
                        "schedule": {
                            "days": ["mon"],
                            "recurrence": "custom_days",
                            "state": "never",
                            "time": None,
                        },
                    },
                },
                "key": DOMAIN,
                "version": store.STORAGE_VERSION,
                "minor_version": store.STORAGE_VERSION_MINOR,
            },
        }
    )
    assert await async_setup_component(hass, DOMAIN, {})

    get_agents_mock = AsyncMock(return_value=[BackupAgentTest("agent", backups=[])])
    register_listener_mock = Mock()

    await setup_backup_platform(
        hass,
        domain="test",
        platform=Mock(
            async_get_backup_agents=get_agents_mock,
            async_register_backup_agents_listener=register_listener_mock,
        ),
    )
    await hass.async_block_till_done()

    reload_backup_agents = register_listener_mock.call_args[1]["listener"]

    client = await hass_client()

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
        {"agent_id": "test.agent", "name": "agent"},
    ]

    repair_issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)
    assert not repair_issue

    # Reload the agents with no agents returned.

    get_agents_mock.return_value = []
    reload_backup_agents()
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id({"type": "backup/agents/info"})
    resp = await ws_client.receive_json()
    assert resp["result"]["agents"] == [
        {"agent_id": "backup.local", "name": "local"},
    ]

    repair_issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)
    assert repair_issue

    # Start the repair flow.

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": issue_id},
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
        "description_placeholders": {"agent_id": "test.agent"},
        "last_step": None,
        "preview": None,
    }

    # Aborting the flow should not remove the issue and not update the config.

    resp = await client.delete(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {"message": "Flow aborted"}

    resp = await client.get(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.NOT_FOUND
    data = await resp.json()

    repair_issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)
    assert repair_issue

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == ["test.agent"]

    # Start the repair flow again.

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": issue_id},
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
        "description_placeholders": {"agent_id": "test.agent"},
        "last_step": None,
        "preview": None,
    }

    # Finish the flow.

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "description": None,
        "description_placeholders": None,
        "title": "",
    }

    assert not issue_registry.async_get_issue(
        domain=DOMAIN, issue_id="automatic_backup_agents_not_loaded"
    )

    await ws_client.send_json_auto_id({"type": "backup/config/info"})
    result = await ws_client.receive_json()
    assert result["result"]["config"]["create_backup"]["agent_ids"] == []
