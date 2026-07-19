"""Test the Somfy MyLink cover platform."""

from unittest.mock import MagicMock

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    CoverDeviceClass,
    CoverState,
)
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, mock_restore_cache

LEFT_ENTITY = "cover.left_shade"
LEFT_TARGET = "CE1A2B3C.1"
RIGHT_ENTITY = "cover.right_shade"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and set up a config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _call(hass: HomeAssistant, service: str, entity_id: str) -> None:
    """Call a cover service and wait for it to finish."""
    await hass.services.async_call(
        COVER_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_open_calls_move_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test opening a cover sends move_up."""
    await _setup(hass, mock_config_entry)
    await _call(hass, SERVICE_OPEN_COVER, LEFT_ENTITY)
    mock_somfy_mylink.move_up.assert_awaited_once_with(LEFT_TARGET)
    mock_somfy_mylink.move_down.assert_not_awaited()


async def test_close_calls_move_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test closing a cover sends move_down."""
    await _setup(hass, mock_config_entry)
    await _call(hass, SERVICE_CLOSE_COVER, LEFT_ENTITY)
    mock_somfy_mylink.move_down.assert_awaited_once_with(LEFT_TARGET)
    mock_somfy_mylink.move_up.assert_not_awaited()


async def test_stop_calls_move_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test stopping a cover sends move_stop."""
    await _setup(hass, mock_config_entry)
    await _call(hass, SERVICE_STOP_COVER, LEFT_ENTITY)
    mock_somfy_mylink.move_stop.assert_awaited_once_with(LEFT_TARGET)


async def test_reverse_swaps_direction(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test the reversed option swaps open and close commands."""
    config_entry = MockConfigEntry(
        domain="somfy_mylink",
        title="MyLink 192.168.1.10",
        data={"host": "192.168.1.10", "port": 44100, "system_id": "sid-123"},
        options={"reversed_target_ids": {LEFT_TARGET: True}},
    )
    await _setup(hass, config_entry)

    await _call(hass, SERVICE_OPEN_COVER, LEFT_ENTITY)
    mock_somfy_mylink.move_down.assert_awaited_once_with(LEFT_TARGET)

    await _call(hass, SERVICE_CLOSE_COVER, LEFT_ENTITY)
    mock_somfy_mylink.move_up.assert_awaited_once_with(LEFT_TARGET)


async def test_device_classes_and_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cover device classes are mapped and unique ids preserved."""
    await _setup(hass, mock_config_entry)

    left = hass.states.get(LEFT_ENTITY)
    right = hass.states.get(RIGHT_ENTITY)
    assert left.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.BLIND
    assert right.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER

    assert entity_registry.async_get(LEFT_ENTITY).unique_id == LEFT_TARGET


async def test_restore_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_somfy_mylink: MagicMock,
) -> None:
    """Test the last open/closed state is restored on startup."""
    mock_restore_cache(hass, (State(LEFT_ENTITY, CoverState.CLOSED),))
    await _setup(hass, mock_config_entry)

    assert hass.states.get(LEFT_ENTITY).state == CoverState.CLOSED
