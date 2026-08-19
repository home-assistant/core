"""Tests for the WeatherFlow Cloud sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from weatherflow4py.models.rest.observation import ObservationStationREST

from homeassistant.components.weatherflow_cloud.const import DOMAIN
from homeassistant.components.weatherflow_cloud.coordinator import (
    WeatherFlowObservationCoordinator,
    WeatherFlowWindCoordinator,
)
from homeassistant.components.weatherflow_cloud.sensor import (
    WeatherFlowWebsocketSensorObservation,
    WeatherFlowWebsocketSensorWind,
    _battery_percentage,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_fixture,
    snapshot_platform,
)


@pytest.mark.parametrize(
    ("voltage", "percentage"),
    [
        pytest.param(1.9, 0, id="below-minimum"),
        pytest.param(2.45, 85, id="interpolated"),
        pytest.param(2.8, 100, id="above-maximum"),
    ],
)
def test_battery_percentage(voltage: float, percentage: float) -> None:
    """Test converting battery voltage to percentage."""
    assert _battery_percentage(voltage) == pytest.approx(percentage)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "24432"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "172"


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


async def test_rest_sensor_unavailable_with_empty_observation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test REST sensors are unavailable when no current observation is returned."""
    with patch(
        "homeassistant.components.weatherflow_cloud.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.my_home_station_temperature").state == "10.5"

    all_data = await mock_rest_api.get_all_data()
    all_data[24432].observation = replace(all_data[24432].observation, obs=[])
    mock_rest_api.get_all_data.return_value = all_data

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.my_home_station_temperature").state == STATE_UNAVAILABLE
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
    coordinator.stations = mock_rest_api.async_get_stations.return_value

    # Mock the coordinator data structure
    test_station_id = 24432
    test_device_id = 12345
    test_data = {
        "battery": 2.45,
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

    entity_description.value_fn = lambda data: data["battery"]
    assert sensor.native_value == 2.45


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
    coordinator.stations = mock_rest_api.async_get_stations.return_value

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
