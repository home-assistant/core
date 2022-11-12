"""Tests for sensors used to report data from the combined energy API."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from combined_energy import models
import pytest

from homeassistant.components.combined_energy import sensor
from homeassistant.components.combined_energy.coordinator import (
    CombinedEnergyConnectivityDataService,
    CombinedEnergyReadingsDataService,
)
from homeassistant.components.sensor import SensorEntityDescription

from .common import mock_device


class TestCombinedEnergyConnectedSensor:
    """Test cases for CombinedEnergyConnectedSensor."""

    @pytest.fixture
    def data_service(self):
        """Mock data service."""
        return AsyncMock(
            CombinedEnergyConnectivityDataService,
            api=AsyncMock(installation_id=999999),
            coordinator=AsyncMock(),
        )

    def test_initialise(self, data_service):
        """Test initialisation generates expected names."""
        target = sensor.CombinedEnergyConnectedSensor("Test", data_service)

        assert target.unique_id == "install_999999-connected"

    def test_is_on__where_no_data(self, data_service):
        """Test is_on where no data has been collected."""
        data_service.data = None
        target = sensor.CombinedEnergyConnectedSensor("Test", data_service)

        actual = target.is_on

        assert actual is None

    @pytest.mark.parametrize("connected", (True, False))
    def test_is_on__where_connected_status_set(self, data_service, connected):
        """Test is_on where Connected status is set."""
        data_service.data = models.ConnectionStatus(
            status="OK",
            installationId=999999,
            connected=connected,
            since=datetime(2022, 11, 11, 11, 11, 11),
        )
        target = sensor.CombinedEnergyConnectedSensor("Test", data_service)

        actual = target.is_on

        assert actual is connected


def mock_description(key: str, name="Test Sensor") -> SensorEntityDescription:
    """Generate a mock entity description."""
    return SensorEntityDescription(
        key=key,
        name=name,
    )


class TestCombinedEnergyReadings:
    """Tests for various implementations of readings sensors."""

    @pytest.fixture
    def data_service(self):
        """Mock data service."""
        return AsyncMock(
            CombinedEnergyReadingsDataService,
            api=AsyncMock(installation_id=999999),
            coordinator=AsyncMock(),
            data={
                13: Mock(
                    models.DeviceReadings,
                    generic_value=[12.345, 67.896],
                    energy_value=[0.01, 0.02],
                    power_value=3.456,
                    power_factor_value=[0.57, -0.9967],
                    water_volume_value=[123.0, 126.7],
                ),
            },
        )

    @pytest.mark.parametrize(
        "sensor_type, key, expected",
        (
            (sensor.GenericSensor, "generic_value", 67.9),
            (sensor.EnergySensor, "energy_value", 0.03),
            (sensor.PowerSensor, "power_value", 3.46),
            (sensor.PowerFactorSensor, "power_factor_value", -99.7),
            (sensor.WaterVolumeSensor, "water_volume_value", 127),
        ),
    )
    def test_native_value(
        self, hass, installation, data_service, sensor_type, key, expected
    ):
        """Test that native values are correctly cast."""
        factory = sensor.CombinedEnergyReadingsSensorFactory(
            hass, installation, data_service
        )
        device = mock_device(models.DeviceType.EnergyBalance)
        device_info = factory._generate_device_info(device)
        description = mock_description(key)
        target = sensor_type(device, device_info, description, data_service)

        actual = target.native_value

        assert actual == expected
        assert target.available
