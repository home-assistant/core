"""Tests for the Disneyland Paris sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from dlpwait import DLPWaitError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Disneyland Paris sensor entities."""

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("sensor.disneyland_park_opening_time"),
        ("sensor.disneyland_park_closing_time"),
        ("sensor.disneyland_buzz_lightyear_laser_blast_standby_wait_time"),
        ("sensor.disney_adventure_world_park_opening_time"),
        ("sensor.disney_adventure_world_park_closing_time"),
        (
            "sensor.disney_adventure_world_the_twilight_zone_tower_of_terror_standby_wait_time"
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_disneyland_paris_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test API error causes entities to become unavailable."""

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    mock_disneyland_paris_client.update.side_effect = DLPWaitError()

    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("sensor.disneyland_park_opening_time"),
        ("sensor.disneyland_park_closing_time"),
        ("sensor.disneyland_buzz_lightyear_laser_blast_standby_wait_time"),
        ("sensor.disney_adventure_world_park_opening_time"),
        ("sensor.disney_adventure_world_park_closing_time"),
        (
            "sensor.disney_adventure_world_the_twilight_zone_tower_of_terror_standby_wait_time"
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities_unknown_on_incomplete_data(
    hass: HomeAssistant,
    mock_disneyland_paris_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test incomplete API response causes entities to become unknown."""

    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])

    mock_disneyland_paris_client.parks = {}

    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
