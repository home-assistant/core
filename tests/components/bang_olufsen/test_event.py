"""Test the bang_olufsen event entities."""

from unittest.mock import AsyncMock

from inflection import underscore
from mozart_api.models import ButtonEvent

from homeassistant.components.bang_olufsen.const import (
    DEVICE_BUTTON_EVENTS,
    DEVICE_BUTTONS,
    EVENT_TRANSLATION_MAP,
)
from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import TEST_BUTTON_EVENT_ENTITY_ID

from tests.common import MockConfigEntry


async def test_button_event_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test button event entities are created."""

    # Load entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Add Button Event entity ids
    entity_ids = [
        f"event.beosound_balance_11111111_{underscore(button_type)}".replace(
            "preset", "preset_"
        )
        for button_type in DEVICE_BUTTONS
    ]

    # Check that the entities are available
    for entity_id in entity_ids:
        entity_registry.async_get(entity_id)


async def test_button_event_creation_beoconnect_core(
    hass: HomeAssistant,
    mock_config_entry_core: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test button event entities are not created when using a Beoconnect Core."""

    # Load entry
    mock_config_entry_core.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_core.entry_id)

    # Add Button Event entity ids
    entity_ids = [
        f"event.beosound_balance_11111111_{underscore(button_type)}".replace(
            "preset", "preset_"
        )
        for button_type in DEVICE_BUTTONS
    ]

    # Check that the entities are unavailable
    for entity_id in entity_ids:
        assert not entity_registry.async_get(entity_id)


async def test_button(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test button event entity."""
    # Load entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Enable the entity
    entity_registry.async_update_entity(TEST_BUTTON_EVENT_ENTITY_ID, disabled_by=None)
    hass.config_entries.async_schedule_reload(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_BUTTON_EVENT_ENTITY_ID))
    assert states.state is STATE_UNKNOWN
    assert states.attributes[ATTR_EVENT_TYPES] == list(DEVICE_BUTTON_EVENTS)

    # Check button reacts as expected to WebSocket events
    notification_callback = mock_mozart_client.get_button_notifications.call_args[0][0]

    notification_callback(ButtonEvent(button="PlayPause", state="shortPress (Release)"))
    await hass.async_block_till_done()

    assert (states := hass.states.get(TEST_BUTTON_EVENT_ENTITY_ID))
    assert states.state is not None
    assert (
        states.attributes[ATTR_EVENT_TYPE]
        == EVENT_TRANSLATION_MAP["shortPress (Release)"]
    )
