"""Tests for the Huum light entity."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "light.huum_sauna_light"


async def test_light(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_light_turn_off(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off light."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        Platform.LIGHT,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_huum.toggle_light.assert_called_once()


async def test_light_turn_on(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on light."""
    mock_huum.light = 0

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.LIGHT])

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        Platform.LIGHT,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_huum.toggle_light.assert_called_once()
