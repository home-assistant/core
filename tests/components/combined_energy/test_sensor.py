"""Tests for sensors used to report data from the combined energy API."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from combined_energy import models
import pytest

from homeassistant.components.combined_energy import sensor
from homeassistant.components.combined_energy.coordinator import (
    CombinedEnergyReadingsCoordinator,
)

from .common import mock_device


def mock_description(
    key: str, native_value_fn=None, name: str = "Test Sensor"
) -> sensor.CombinedEnergySensorEntityDescription:
    """Generate a mock entity description."""
    return sensor.CombinedEnergySensorEntityDescription(
        key=key,
        name=name,
        native_value_fn=native_value_fn,
    )


class TestCombinedEnergyReadingsSensor:
    """Tests for combined energy readings sensor."""

    @pytest.fixture
    def coordinator(self):
        """Mock data service."""
        return AsyncMock(
            CombinedEnergyReadingsCoordinator,
            api=AsyncMock(installation_id=999999),
            coordinator=AsyncMock(),
            data={
                13: Mock(
                    models.DeviceReadings,
                    range_start=datetime(2022, 11, 11, 11, 11, 11),
                    no_value=None,
                    generic_value=[12.345, 67.896],
                    energy_value=[0.01, 0.02],
                    power_value=3.456,
                    power_factor_value=[0.57, -0.9967],
                    water_volume_value=[123.0, 126.7],
                ),
            },
            last_update_success=True,
        )

    def test_available__where_device_and_entity_is_found(self, hass, coordinator):
        """Test available is True when device and entity are found."""
        device = mock_device(models.DeviceType.EnergyBalance, device_id=13)
        description = mock_description("energy_value")
        target = sensor.CombinedEnergyReadingsSensor(device, description, coordinator)

        actual = target.available

        assert actual is True

    def test_available__where_no_data_is_returned(self, hass, coordinator):
        """Test available is False when no data is returned."""
        device = mock_device(models.DeviceType.EnergyBalance, device_id=7)
        description = mock_description("energy_value")
        coordinator.data = None
        target = sensor.CombinedEnergyReadingsSensor(device, description, coordinator)

        actual = target.available

        assert actual is False

    def test_available__where_device_is_not_found(self, hass, coordinator):
        """Test available is False when device is not found."""
        device = mock_device(models.DeviceType.EnergyBalance, device_id=7)
        description = mock_description("energy_value")
        target = sensor.CombinedEnergyReadingsSensor(device, description, coordinator)

        actual = target.available

        assert actual is False

    def test_available__where_device_is_found_but_entity_is_not(
        self, hass, coordinator
    ):
        """Test available is False when device is found but entity is not."""
        device = mock_device(models.DeviceType.EnergyBalance, device_id=13)
        description = mock_description("foo_value")
        target = sensor.CombinedEnergyReadingsSensor(device, description, coordinator)

        actual = target.available

        assert actual is False

    @pytest.mark.parametrize(
        ("device_id", "description", "expected"),
        (
            (
                13,
                sensor.CombinedEnergySensorEntityDescription(
                    key="foo",
                    suggested_display_precision=2,
                    native_value_fn=sensor._generic_native_value,
                ),
                None,
            ),
            (
                13,
                sensor.CombinedEnergySensorEntityDescription(
                    key="generic_value",
                    suggested_display_precision=2,
                    native_value_fn=sensor._generic_native_value,
                ),
                67.9,
            ),
            (
                13,
                sensor.CombinedEnergySensorEntityDescription(
                    key="energy_value",
                    suggested_display_precision=2,
                    native_value_fn=sensor._energy_native_value,
                ),
                0.03,
            ),
            (
                13,
                sensor.CombinedEnergySensorEntityDescription(
                    key="power_factor_value",
                    suggested_display_precision=1,
                    native_value_fn=sensor._power_factor_native_value,
                ),
                -99.7,
            ),
            (
                13,
                sensor.CombinedEnergySensorEntityDescription(
                    key="water_volume_value",
                    suggested_display_precision=0,
                    native_value_fn=sensor._water_volume_native_value,
                ),
                127,
            ),
        ),
    )
    def test_native_value(self, hass, coordinator, device_id, description, expected):
        """Test native value is correct."""
        device = mock_device(models.DeviceType.EnergyBalance, device_id=device_id)
        target = sensor.CombinedEnergyReadingsSensor(device, description, coordinator)

        actual = target.native_value

        assert actual == expected

    @pytest.mark.parametrize(
        ("device_id", "expected"),
        (
            (13, datetime(2022, 11, 11, 11, 11, 11)),
            (42, None),
        ),
    )
    def test_energy_sensor_last_reset(
        self, hass, installation, coordinator, device_id, expected
    ) -> None:
        """Test last reset value is correct for energy sensors."""
        device = mock_device(models.DeviceType.EnergyBalance, device_id=device_id)
        description = mock_description("energy_value")
        target = sensor.CombinedEnergyReadingsSensor(device, description, coordinator)

        actual = target.last_reset

        assert actual == expected
