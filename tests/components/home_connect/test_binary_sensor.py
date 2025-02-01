"""Tests for home_connect binary_sensor entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from aiohomeconnect.model import ArrayOfEvents, Event, EventKey, EventMessage, EventType
import pytest

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.home_connect.const import (
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensors(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Test binary sensor entities."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED


async def test_binary_sensors_entity_availabilty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    appliance_ha_id: str,
) -> None:
    """Test if binary sensor entities availability are based on the appliance connection state."""
    entity_ids = [
        "binary_sensor.washer_door",
        "binary_sensor.washer_remote_control",
    ]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BSH_DOOR_STATE_CLOSED, "off"),
        (BSH_DOOR_STATE_LOCKED, "off"),
        (BSH_DOOR_STATE_OPEN, "on"),
        ("", STATE_UNKNOWN),
    ],
)
async def test_binary_sensors_door_states(
    appliance_ha_id: str,
    expected: str,
    value: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Tests for Appliance door states."""
    entity_id = "binary_sensor.washer_door"
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED

    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            key=EventKey.BSH_COMMON_STATUS_DOOR_STATE,
                            raw_key=EventKey.BSH_COMMON_STATUS_DOOR_STATE.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=value,
                        )
                    ],
                ),
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.parametrize(
    ("entity_id", "event_key", "event_value_update", "expected", "appliance_ha_id"),
    [
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            False,
            STATE_OFF,
            "Washer",
        ),
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            True,
            STATE_ON,
            "Washer",
        ),
        (
            "binary_sensor.washer_remote_control",
            EventKey.BSH_COMMON_STATUS_REMOTE_CONTROL_ACTIVE,
            "",
            STATE_UNKNOWN,
            "Washer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_CLOSED,
            STATE_OFF,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            REFRIGERATION_STATUS_DOOR_OPEN,
            STATE_ON,
            "FridgeFreezer",
        ),
        (
            "binary_sensor.fridgefreezer_refrigerator_door",
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            "",
            STATE_UNKNOWN,
            "FridgeFreezer",
        ),
    ],
    indirect=["appliance_ha_id"],
)
async def test_binary_sensors_functionality(
    entity_id: str,
    event_key: EventKey,
    event_value_update: str,
    appliance_ha_id: str,
    expected: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
) -> None:
    """Tests for Home Connect Fridge appliance door states."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED
    await client.add_events(
        [
            EventMessage(
                appliance_ha_id,
                EventType.STATUS,
                ArrayOfEvents(
                    [
                        Event(
                            key=event_key,
                            raw_key=event_key.value,
                            timestamp=0,
                            level="",
                            handling="",
                            value=event_value_update,
                        )
                    ],
                ),
            )
        ]
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_create_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    setup_credentials: None,
    client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    entity_id = "binary_sensor.washer_door"
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
    assert await integration_setup(client)
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
