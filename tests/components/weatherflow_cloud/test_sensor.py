"""Tests for the WeatherFlow Cloud sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion
from weatherflow4py.models.rest.observation import ObservationStationREST

from homeassistant.components.weatherflow_cloud import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_all_entities_with_lightning_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""

    get_observation_response_data = ObservationStationREST.from_json(
        load_fixture("station_observation_error.json", DOMAIN)
    )

    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

        assert (
            hass.states.get("sensor.my_home_station_lightning_last_strike").state
            == "2024-02-07T23:01:15+00:00"
        )

        # Update the data in our API
        all_data = await mock_api.get_all_data()
        all_data[24432].observation = get_observation_response_data
        mock_api.get_all_data.return_value = all_data

        # Move time forward
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.my_home_station_lightning_last_strike").state
            == STATE_UNKNOWN
        )
