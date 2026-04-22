"""Tests for Insteon event entities."""

from unittest.mock import patch

import pytest

from homeassistant.components import insteon
from homeassistant.components.event import ATTR_EVENT_TYPE, DATA_COMPONENT
from homeassistant.components.insteon import (
    entity as insteon_entity,
    event as insteon_event_module,
    utils as insteon_utils,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry

devices = MockDevices()


@pytest.fixture(autouse=True)
def event_platform_only():
    """Only setup the event platform to speed up tests."""
    with patch(
        "homeassistant.components.insteon.INSTEON_PLATFORMS",
        (Platform.EVENT,),
    ):
        yield


@pytest.fixture(autouse=True)
def patch_setup_and_devices():
    """Patch the Insteon setup process and devices."""
    with (
        patch.object(insteon, "async_connect", new=mock_connection),
        patch.object(insteon, "async_close"),
        patch.object(insteon, "devices", devices),
        patch.object(insteon_utils, "devices", devices),
        patch.object(insteon_entity, "devices", devices),
    ):
        yield


async def mock_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


async def test_event_listeners_unsubscribed(hass: HomeAssistant) -> None:
    """Ensure event listeners are unsubscribed when integration is unloaded."""

    config_entry = MockConfigEntry(domain=insteon.DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    # Set up the integration which should register event listeners
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Patch Event.unsubscribe to observe unsubscription calls during unload
    with patch("pyinsteon.events.Event.unsubscribe") as unsubscribe_mock:
        # Explicitly unload the event component for this config entry which
        # should remove entities and unsubscribe listeners.
        event_component = hass.data[DATA_COMPONENT]
        await event_component.async_unload_entry(config_entry)
        await hass.async_block_till_done()

    assert unsubscribe_mock.call_count > 0


async def test_event_entity_triggers_event(hass: HomeAssistant) -> None:
    """Test that an Insteon event listener triggers the event entity."""

    config_entry = MockConfigEntry(domain=insteon.DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Find any event entity created for the mock devices
    entity_id = None
    for state in hass.states.async_all():
        if state.entity_id.startswith("event.device_33_33_33"):
            entity_id = state.entity_id
            break

    assert entity_id is not None

    event_component = hass.data[DATA_COMPONENT]
    entity = event_component.get_entity(entity_id)

    # There should be at least one registered listener
    listeners = getattr(entity, "_insteon_event_listeners", [])
    assert listeners

    # Trigger the first listener and verify the entity state updates
    event_obj, listener = listeners[0]
    listener(event_obj.name, event_obj.address, event_obj.group, "button_b")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == event_obj.name.removesuffix("_event")


async def test_event_entity_handles_button_event(hass: HomeAssistant) -> None:
    """Test that the event entity handles a button event from _BUTTON_EVENT_NAMES."""

    config_entry = MockConfigEntry(domain=insteon.DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Locate an event entity for the mock device
    entity_id = None
    for state in hass.states.async_all():
        if state.entity_id.startswith("event.device_33_33_33"):
            entity_id = state.entity_id
            break

    assert entity_id is not None

    event_component = hass.data["event"]
    entity = event_component.get_entity(entity_id)

    listeners = getattr(entity, "_insteon_event_listeners", [])
    assert listeners

    event_obj, listener = listeners[0]

    # Find a button event name matching this event object
    button_name = None
    for btn in insteon_event_module._BUTTON_EVENT_NAMES:
        if btn == event_obj.name:
            button_name = btn
            break

    if button_name is None:
        pytest.skip("No button event name for this event object")

    # Trigger the listener with a button press and verify attribute
    listener(button_name, event_obj.address, event_obj.group, "button_b")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == button_name.removesuffix("_event")
