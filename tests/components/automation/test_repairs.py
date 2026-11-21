"""Test automation repairs."""

import copy
from unittest.mock import patch

import pytest
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import automation
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.config import AUTOMATION_CONFIG_PATH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import dump, load_yaml

AUTOMATION_CONFIG = {
    "id": "test_1",
    "alias": "test automation",
    "trigger": {"trigger": "state", "entity_id": "binary_sensor.old"},
    "action": {
        "action": "test.automation",
        "target": {"entity_id": "binary_sensor.old"},
    },
}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use a temporary config directory for this test module."""
    return hass_tmp_config_dir


async def test_entity_renamed_creates_fixable_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test renaming an entity creates an issue on referencing automations."""
    assert await async_setup_component(
        hass, automation.DOMAIN, {automation.DOMAIN: [copy.deepcopy(AUTOMATION_CONFIG)]}
    )
    await hass.async_block_till_done()

    entry = entity_registry.async_get_or_create(
        "binary_sensor", "test", "uid", suggested_object_id="old"
    )
    assert entry.entity_id == "binary_sensor.old"
    entity_registry.async_update_entity(
        entry.entity_id, new_entity_id="binary_sensor.new"
    )
    await hass.async_block_till_done()

    automation_entity_id = entity_registry.async_get_entity_id(
        automation.DOMAIN, automation.DOMAIN, "test_1"
    )
    assert automation_entity_id is not None
    issue = issue_registry.async_get_issue(
        automation.DOMAIN,
        f"{automation_entity_id}_entity_renamed_binary_sensor.old",
    )
    assert issue is not None
    assert issue.is_fixable
    assert issue.is_persistent
    assert issue.data["config_id"] == "test_1"
    assert issue.data["old_entity_id"] == "binary_sensor.old"
    assert issue.data["new_entity_id"] == "binary_sensor.new"


async def test_entity_renamed_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix flow rewrites the stored config and reloads the automation."""
    path = hass.config.path(AUTOMATION_CONFIG_PATH)

    def _write_config() -> None:
        with open(path, "w", encoding="utf-8") as file:
            file.write(dump([copy.deepcopy(AUTOMATION_CONFIG)]))

    await hass.async_add_executor_job(_write_config)

    assert await async_setup_component(
        hass, automation.DOMAIN, {automation.DOMAIN: [copy.deepcopy(AUTOMATION_CONFIG)]}
    )
    await hass.async_block_till_done()

    entry = entity_registry.async_get_or_create(
        "binary_sensor", "test", "uid", suggested_object_id="old"
    )
    entity_registry.async_update_entity(
        entry.entity_id, new_entity_id="binary_sensor.new"
    )
    await hass.async_block_till_done()

    automation_entity_id = entity_registry.async_get_entity_id(
        automation.DOMAIN, automation.DOMAIN, "test_1"
    )
    issue_id = f"{automation_entity_id}_entity_renamed_binary_sensor.old"
    assert issue_registry.async_get_issue(automation.DOMAIN, issue_id)

    assert await async_setup_component(hass, REPAIRS_DOMAIN, {})
    client = await hass_client()
    data = await start_repair_fix_flow(client, automation.DOMAIN, issue_id)
    assert data["step_id"] == "confirm"

    reloaded_config = copy.deepcopy(AUTOMATION_CONFIG)
    reloaded_config["trigger"] = {
        "trigger": "state",
        "entity_id": "binary_sensor.new",
    }
    reloaded_config["action"] = {
        "action": "test.automation",
        "target": {"entity_id": "binary_sensor.new"},
    }
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={automation.DOMAIN: [reloaded_config]},
    ):
        data = await process_repair_fix_flow(client, data["flow_id"])
        await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert issue_registry.async_get_issue(automation.DOMAIN, issue_id) is None

    updated = load_yaml(path)
    assert updated[0]["trigger"]["entity_id"] == "binary_sensor.new"
    assert updated[0]["action"]["target"]["entity_id"] == "binary_sensor.new"
