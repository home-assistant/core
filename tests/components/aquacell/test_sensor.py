"""Test the Aquacell init module."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aquacell.const import STALE_DATA_TIMEOUT, UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.aquacell_name_battery"
LAST_UPDATE_ENTITY_ID = "sensor.aquacell_name_last_update"
# Matches lastUpdate in the softener fixture
LAST_UPDATE = "2024-05-10 07:44:30+00:00"


@pytest.mark.freeze_time(LAST_UPDATE)
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


@pytest.mark.freeze_time(LAST_UPDATE)
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
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_aquacell_api.get_all_softeners.return_value = softeners
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == "40"


@pytest.mark.freeze_time(LAST_UPDATE)
async def test_sensors_unavailable_when_data_is_stale(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_aquacell_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors become unavailable when the softener stops reporting."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == "40"

    freezer.tick(STALE_DATA_TIMEOUT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(LAST_UPDATE_ENTITY_ID).state == "2024-05-10T07:44:30+00:00"

    softener = mock_aquacell_api.get_all_softeners.return_value[0]
    softener.diagnostics.last_update = dt_util.utcnow()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == "40"
