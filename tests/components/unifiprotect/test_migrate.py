"""Test the UniFi Protect setup flow."""

from unittest.mock import patch

from uiprotect.data import Camera

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .utils import MockUFPFixture, init_entry

from tests.typing import WebSocketGenerator


async def test_deprecated_entity(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
    doorbell: Camera,
) -> None:
    """Test Deprecate entity repair does not exist by default (new installs)."""

    await init_entry(hass, ufp, [doorbell])

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


async def test_migrate_insecure_camera_redirected(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A legacy insecure camera entity is redirected to the secure stream."""
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    # the insecure entity now carries the secure unique_id (history preserved)
    migrated = entity_registry.async_get(insecure.entity_id)
    assert migrated is not None
    assert migrated.unique_id == f"{doorbell.mac}_0"
    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0_insecure"
        )
        is None
    )


async def test_migrate_insecure_camera_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A redundant, unused insecure entity is removed silently."""
    entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(insecure.entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0"
        )
        is not None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"insecure_camera_removed_{doorbell.mac}_0_insecure"
        )
        is None
    )


async def test_migrate_insecure_camera_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Removing an insecure entity that is still used raises an actionable repair."""
    secure = entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, insecure.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(insecure.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"insecure_camera_removed_{doorbell.mac}_0_insecure"
    )
    assert issue is not None
    assert issue.translation_placeholders["entity_id"] == insecure.entity_id
    assert issue.translation_placeholders["replacement"] == secure.entity_id


async def test_migrate_insecure_camera_removed_disabled_not_repaired(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A disabled insecure entity is removed without a repair even if referenced."""
    entity_registry.async_get_or_create(
        Platform.CAMERA, DOMAIN, f"{doorbell.mac}_0", config_entry=ufp.entry
    )
    insecure = entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"{doorbell.mac}_0_insecure",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await _load_automation(hass, insecure.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(insecure.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"insecure_camera_removed_{doorbell.mac}_0_insecure"
        )
        is None
    )


async def test_migrate_package_binary_sensor_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """An unused package binary sensor is removed silently."""
    package = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_smart_obj_package",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(package.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"package_binary_sensor_removed_{doorbell.mac}_smart_obj_package"
        )
        is None
    )


async def test_migrate_package_binary_sensor_removed_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Removing a used package binary sensor raises an actionable repair."""
    package = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_smart_obj_package",
        config_entry=ufp.entry,
    )
    await _load_automation(hass, package.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(package.entity_id) is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"package_binary_sensor_removed_{doorbell.mac}_smart_obj_package"
    )
    assert issue is not None
    assert issue.translation_placeholders["entity_id"] == package.entity_id


async def test_migrate_package_binary_sensor_removed_disabled_not_repaired(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """A disabled package binary sensor is removed without a repair even if referenced."""
    package = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{doorbell.mac}_smart_obj_package",
        config_entry=ufp.entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await _load_automation(hass, package.entity_id)

    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    assert entity_registry.async_get(package.entity_id) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"package_binary_sensor_removed_{doorbell.mac}_smart_obj_package"
        )
        is None
    )
