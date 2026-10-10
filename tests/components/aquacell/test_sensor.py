"""Test the Aquacell init module."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aquacell.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.aquacell_name_battery"


async def test_sensors(
    hass: HomeAssistant,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of Aquacell sensors."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_unavailable_when_softener_missing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors become unavailable when the softener is no longer returned."""
    await setup_integration(hass, mock_config_entry)
    softeners = mock_aquacell_api.get_all_softeners.return_value
    assert hass.states.get(ENTITY_ID).state == "40"

    mock_aquacell_api.get_all_softeners.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_aquacell_api.get_all_softeners.return_value = softeners
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "40"
