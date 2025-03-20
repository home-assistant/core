"""Test for the SmartThings binary_sensor platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.smartthings import DOMAIN
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

    assert hass.states.get("binary_sensor.refrigerator_door").state == STATE_OFF

    await trigger_update(
        hass,
        devices,
        "7db87911-7dce-1cf2-7119-b953432a2f09",
        Capability.CONTACT_SENSOR,
        Attribute.CONTACT,
        "open",
    )

    assert hass.states.get("binary_sensor.refrigerator_door").state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["virtual_valve"])
async def test_create_issue(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    entity_id = "binary_sensor.volvo_valve"
    issue_id = f"deprecated_binary_valve_{entity_id}"

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
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

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0
