"""Tests for home_connect binary_sensor entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectAPI
import pytest

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.home_connect.const import (
    BSH_DOOR_STATE,
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
    REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("bypass_throttle")
async def test_binary_sensors(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Test binary sensor entities."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (BSH_DOOR_STATE_CLOSED, "off"),
        (BSH_DOOR_STATE_LOCKED, "off"),
        (BSH_DOOR_STATE_OPEN, "on"),
        ("", "unavailable"),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_binary_sensors_door_states(
    expected: str,
    state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Tests for Appliance door states."""
    entity_id = "binary_sensor.washer_door"
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.status.update({BSH_DOOR_STATE: {"value": state}})
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.parametrize(
    ("entity_id", "status_key", "event_value_update", "expected", "appliance"),
    [
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_CLOSED,
            STATE_OFF,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_OPEN,
            STATE_ON,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
            "",
            STATE_UNAVAILABLE,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance"],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_bianry_sensors_fridge_door_states(
    entity_id: str,
    status_key: str,
    event_value_update: str,
    appliance: Mock,
    expected: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Tests for Home Connect Fridge appliance door states."""
    appliance.status.update(
        HomeConnectAPI.json2dict(
            load_json_object_fixture("home_connect/status.json")["data"]["status"]
        )
    )
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    appliance.status.update({status_key: {"value": event_value_update}})
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("bypass_throttle")
async def test_create_issue(
    hass: HomeAssistant,
    appliance: Mock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    entity_id = "binary_sensor.washer_door"
    get_appliances.return_value = [appliance]
    issue_id = f"deprecated_binary_common_door_sensor_{entity_id}"

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

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.status.update({BSH_DOOR_STATE: {"value": BSH_DOOR_STATE_OPEN}})
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0
