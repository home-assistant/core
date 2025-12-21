"""Test the UniFi Protect setup flow."""

from __future__ import annotations

from unittest.mock import patch

from uiprotect.data import Camera

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .utils import MockUFPFixture, init_entry

from tests.components.repairs import async_process_repairs_platforms
from tests.typing import WebSocketGenerator


async def test_deprecated_entity(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair does not exist by default (new installs)."""

    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


async def test_deprecated_entity_no_automations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair exists for existing installs."""
    entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
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
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


async def _load_automation(hass: HomeAssistant, entity_id: str):
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "alias": "test1",
                    "trigger": [
                        {"platform": "state", "entity_id": entity_id},
                        {
                            "platform": "event",
                            "event_type": "state_changed",
                            "event_data": {"entity_id": entity_id},
                        },
                    ],
                    "condition": {
                        "condition": "state",
                        "entity_id": entity_id,
                        "state": "on",
                    },
                    "action": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": entity_id},
                        },
                    ],
                },
            ]
        },
    )


async def test_deprecate_entity_automation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair exists for existing installs."""
    entry = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, entry.entity_id)
    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={AUTOMATION_DOMAIN: []},
    ):
        await hass.services.async_call(AUTOMATION_DOMAIN, SERVICE_RELOAD, blocking=True)

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


async def _load_script(hass: HomeAssistant, entity_id: str):
    assert await async_setup_component(
        hass,
        SCRIPT_DOMAIN,
        {
            SCRIPT_DOMAIN: {
                "test": {
                    "sequence": {
                        "service": "test.script",
                        "data": {"entity_id": entity_id},
                    }
                }
            },
        },
    )


async def test_deprecate_entity_script(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair exists for existing installs."""
    entry = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
        config_entry=ufp.entry,
    )
    await _load_script(hass, entry.entity_id)
    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={SCRIPT_DOMAIN: {}},
    ):
        await hass.services.async_call(SCRIPT_DOMAIN, SERVICE_RELOAD, blocking=True)

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None
