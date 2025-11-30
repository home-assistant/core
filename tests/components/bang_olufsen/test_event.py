"""Test the bang_olufsen event entities."""

from unittest.mock import AsyncMock

from mozart_api.models import BeoRemoteButton, ButtonEvent, PairedRemoteResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bang_olufsen.const import (
    BEO_REMOTE_KEY_EVENTS,
    DEVICE_BUTTON_EVENTS,
    EVENT_TRANSLATION_MAP,
)
from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import mock_websocket_connection
from .const import (
    TEST_BUTTON_EVENT_ENTITY_ID,
    TEST_REMOTE_KEY_EVENT_ENTITY_ID,
    TEST_SERIAL_NUMBER_3,
)
from .util import get_button_entity_ids, get_remote_entity_ids

from tests.common import MockConfigEntry


async def test_button_event_creation_balance(
    hass: HomeAssistant,
    integration: None,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button event entities are created when using a Balance (Most devices support all buttons like the Balance)."""

    # Add Button Event entity ids
    entity_ids: list[str] = [*get_button_entity_ids(), *get_remote_entity_ids()]

    # Check that the entities are available
    for entity_id in entity_ids:
        assert entity_registry.async_get(entity_id)

    # Check number of entities
    # The media_player entity and all of the button event entities should be the only available
    entity_ids_available = list(entity_registry.entities.keys())
    assert len(entity_ids_available) == 1 + len(entity_ids)

    # Check snapshot
    assert entity_ids_available == snapshot


async def test_no_button_and_remote_key_event_creation(
    hass: HomeAssistant,
    mock_config_entry_core: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button event entities are not created when using a Beoconnect Core with no Beoremote One connected."""
    mock_mozart_client.get_bluetooth_remotes.return_value = PairedRemoteResponse(
        items=[]
    )

    # Load entry
    mock_config_entry_core.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_core.entry_id)
    await mock_websocket_connection(hass, mock_mozart_client)

    # Check number of entities
    # The media_player entity should be the only available
    entity_ids_available = list(entity_registry.entities.keys())
    assert len(entity_ids_available) == 1

    # Check snapshot
    assert entity_ids_available == snapshot


async def test_button_event_creation_beosound_premiere(
    hass: HomeAssistant,
    mock_config_entry_premiere: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Bluetooth button event entity is not created when using a Beosound Premiere."""

    # Load entry
    mock_config_entry_premiere.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_premiere.entry_id)
    await mock_websocket_connection(hass, mock_mozart_client)

    # Add Button Event entity ids
    entity_ids = [
        *get_button_entity_ids("beosound_premiere_33333333"),
        *get_remote_entity_ids(device_serial=TEST_SERIAL_NUMBER_3),
    ]
    entity_ids.remove("event.beosound_premiere_33333333_bluetooth")

    # Check that the entities are available
    for entity_id in entity_ids:
        assert entity_registry.async_get(entity_id)

    # Check number of entities
    # The media_player entity and all of the button event entities (except Bluetooth) should be the only available
    entity_ids_available = list(entity_registry.entities.keys())
    assert len(entity_ids_available) == 1 + len(entity_ids)

    assert entity_ids_available == snapshot


async def test_button(
    hass: HomeAssistant,
    integration: None,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test button event entity."""

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


async def test_remote_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test remote key event entity."""
    # Load entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Enable the entity
    entity_registry.async_update_entity(
        TEST_REMOTE_KEY_EVENT_ENTITY_ID, disabled_by=None
    )
    hass.config_entries.async_schedule_reload(mock_config_entry.entry_id)

    assert (states := hass.states.get(TEST_REMOTE_KEY_EVENT_ENTITY_ID))
    assert states.state is STATE_UNKNOWN
    assert states.attributes[ATTR_EVENT_TYPES] == list(BEO_REMOTE_KEY_EVENTS)

    # Check button reacts as expected to WebSocket events
    notification_callback = (
        mock_mozart_client.get_beo_remote_button_notifications.call_args[0][0]
    )

    notification_callback(BeoRemoteButton(key="Control/Play", type="KeyPress"))
    await hass.async_block_till_done()

    assert (states := hass.states.get(TEST_REMOTE_KEY_EVENT_ENTITY_ID))
    assert states.state is not None
    assert states.attributes[ATTR_EVENT_TYPE] == EVENT_TRANSLATION_MAP["KeyPress"]
