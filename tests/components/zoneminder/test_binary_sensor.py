"""Tests for ZoneMinder binary sensor entities."""

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

ENTITY_ID = "binary_sensor.zm_example_com"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an entity update poll."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the binary sensor entities."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])
    await _poll(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state_updates_on_poll(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the binary sensor follows the server availability."""
    await setup_integration(hass, mock_config_entry, [Platform.BINARY_SENSOR])
    await _poll(hass, freezer)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    type(mock_zoneminder_client).is_available = PropertyMock(return_value=False)
    await _poll(hass, freezer)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF
