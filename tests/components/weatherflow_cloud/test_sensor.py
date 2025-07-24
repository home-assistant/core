"""Tests for the WeatherFlow Cloud sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from weatherflow4py.models.rest.observation import ObservationStationREST

from homeassistant.components.weatherflow_cloud import DOMAIN
from homeassistant.components.weatherflow_cloud.coordinator import (
    WeatherFlowObservationCoordinator,
    WeatherFlowWindCoordinator,
)
from homeassistant.components.weatherflow_cloud.sensor import (
    WeatherFlowWebsocketSensorObservation,
    WeatherFlowWebsocketSensorWind,
)
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_fixture,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities_with_lightning_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""

    get_observation_response_data = ObservationStationREST.from_json(
        await async_load_fixture(hass, "station_observation_error.json", DOMAIN)
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
        all_data = await mock_rest_api.get_all_data()
        all_data[24432].observation = get_observation_response_data
        mock_rest_api.get_all_data.return_value = all_data

        # Move time forward
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.my_home_station_lightning_last_strike").state
            == STATE_UNKNOWN
        )


async def test_websocket_sensor_observation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
) -> None:
    """Test the WebsocketSensorObservation class works."""
    # Set up the integration
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    # Create a mock coordinator with test data
    coordinator = MagicMock(spec=WeatherFlowObservationCoordinator)

    # Mock the coordinator data structure
    test_station_id = 24432
    test_device_id = 12345
    test_data = {
        "temperature": 22.5,
        "humidity": 45,
        "pressure": 1013.2,
    }

    coordinator.data = {test_station_id: {test_device_id: test_data}}

    # Create a sensor entity description
    entity_description = MagicMock()
    entity_description.value_fn = lambda data: data["temperature"]

    # Create the sensor
    sensor = WeatherFlowWebsocketSensorObservation(
        coordinator=coordinator,
        description=entity_description,
        station_id=test_station_id,
        device_id=test_device_id,
    )

    # Test that native_value returns the correct value
    assert sensor.native_value == 22.5


async def test_websocket_sensor_wind(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
) -> None:
    """Test the WebsocketSensorWind class works."""
    # Set up the integration
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    # Create a mock coordinator with test data
    coordinator = MagicMock(spec=WeatherFlowWindCoordinator)

    # Mock the coordinator data structure
    test_station_id = 24432
    test_device_id = 12345
    test_data = {
        "wind_speed": 5.2,
        "wind_direction": 180,
    }

    coordinator.data = {test_station_id: {test_device_id: test_data}}

    # Create a sensor entity description
    entity_description = MagicMock()
    entity_description.value_fn = lambda data: data["wind_speed"]

    # Create the sensor
    sensor = WeatherFlowWebsocketSensorWind(
        coordinator=coordinator,
        description=entity_description,
        station_id=test_station_id,
        device_id=test_device_id,
    )

    # Test that native_value returns the correct value
    assert sensor.native_value == 5.2

    # Test with None data (startup condition)
    coordinator.data = None
    assert sensor.native_value is None
