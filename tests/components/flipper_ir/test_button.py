"""Tests for the Flipper IR button platform."""

from __future__ import annotations

from homeassistant.components.flipper_ir.const import DOMAIN, EVENT_BUTTON_PRESSED
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_PRESS, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_buttons_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A button entity is created for each command with the expected unique id."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries} == {
        f"{mock_config_entry.entry_id}_Power",
        f"{mock_config_entry.entry_id}_Vol_up",
        f"{mock_config_entry.entry_id}_Vol_down",
    }
    assert all(entry.domain == Platform.BUTTON for entry in entries)


async def test_button_press_fires_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Pressing a button fires the Flipper IR button pressed event."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    events: list[Event] = []

    @callback
    def _listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_BUTTON_PRESSED, _listener)

    entry = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{mock_config_entry.entry_id}_Power"
    )
    assert entry is not None

    await hass.services.async_call(
        Platform.BUTTON,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entry},
        blocking=True,
    )

    assert len(events) == 1
    assert events[0].data["entry_id"] == mock_config_entry.entry_id
    assert events[0].data["command"]["name"] == "Power"


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Unloading the entry tears down the platform."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
