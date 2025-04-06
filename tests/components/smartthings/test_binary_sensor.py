"""Test for the SmartThings binary_sensor platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.smartthings import DOMAIN, MAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration, snapshot_smartthings_entities, trigger_update

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(
        hass, entity_registry, snapshot, Platform.BINARY_SENSOR
    )


@pytest.mark.parametrize("device_fixture", ["da_ref_normal_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.refrigerator_cooler_door").state == STATE_OFF

    await trigger_update(
        hass,
        devices,
        "7db87911-7dce-1cf2-7119-b953432a2f09",
        Capability.CONTACT_SENSOR,
        Attribute.CONTACT,
        "open",
        component="cooler",
    )

    assert hass.states.get("binary_sensor.refrigerator_cooler_door").state == STATE_ON


@pytest.mark.parametrize(
    ("device_fixture", "unique_id", "suggested_object_id", "issue_string", "entity_id"),
    [
        (
            "virtual_valve",
            f"612ab3c2-3bb0-48f7-b2c0-15b169cb2fc3_{MAIN}_{Capability.VALVE}_{Attribute.VALVE}_{Attribute.VALVE}",
            "volvo_valve",
            "valve",
            "binary_sensor.volvo_valve",
        ),
        (
            "da_ref_normal_000001",
            f"7db87911-7dce-1cf2-7119-b953432a2f09_{MAIN}_{Capability.CONTACT_SENSOR}_{Attribute.CONTACT}_{Attribute.CONTACT}",
            "refrigerator_door",
            "fridge_door",
            "binary_sensor.refrigerator_door",
        ),
    ],
)
async def test_create_issue_with_items(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    unique_id: str,
    suggested_object_id: str,
    issue_string: str,
    entity_id: str,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    issue_id = f"deprecated_binary_{issue_string}_{entity_id}"

    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test",
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {
                        "entity_id": "automation.test",
                    },
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": [
                        {
                            "condition": "state",
                            "entity_id": entity_id,
                            "state": "on",
                        },
                    ],
                }
            }
        },
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == STATE_OFF

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == f"deprecated_binary_{issue_string}_scripts"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
        "items": "- [test](/config/automation/edit/test)\n- [test](/config/script/edit/test)",
    }

    entity_registry.async_update_entity(
        entity_entry.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize(
    ("device_fixture", "unique_id", "suggested_object_id", "issue_string", "entity_id"),
    [
        (
            "virtual_valve",
            f"612ab3c2-3bb0-48f7-b2c0-15b169cb2fc3_{MAIN}_{Capability.VALVE}_{Attribute.VALVE}_{Attribute.VALVE}",
            "volvo_valve",
            "valve",
            "binary_sensor.volvo_valve",
        ),
        (
            "da_ref_normal_000001",
            f"7db87911-7dce-1cf2-7119-b953432a2f09_{MAIN}_{Capability.CONTACT_SENSOR}_{Attribute.CONTACT}_{Attribute.CONTACT}",
            "refrigerator_door",
            "fridge_door",
            "binary_sensor.refrigerator_door",
        ),
    ],
)
async def test_create_issue(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    unique_id: str,
    suggested_object_id: str,
    issue_string: str,
    entity_id: str,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    issue_id = f"deprecated_binary_{issue_string}_{entity_id}"

    entity_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == STATE_OFF

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == f"deprecated_binary_{issue_string}"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
    }

    entity_registry.async_update_entity(
        entity_entry.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0
