"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.vegehub.const import DOMAIN, OPTION_DATA_TYPE_CHOICES
from homeassistant.components.vegehub.sensor import (
    VegeHubSensor,
    VH400_transform,
    async_setup_entry,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant


@pytest.fixture
def config_entry():
    """Mock a config entry."""
    return MagicMock(
        data={
            "mac_address": "1234567890AB",
            "ip_addr": "192.168.1.10",
            "hub": {"num_channels": 2, "is_ac": 0},
            "hostname": "VegeHub1",
        },
        options={
            "data_type_1": OPTION_DATA_TYPE_CHOICES[1],
            "data_type_2": OPTION_DATA_TYPE_CHOICES[2],
        },
    )


@pytest.fixture
def hass():
    """Mock a HomeAssistant instance."""
    hass_mock = MagicMock()
    hass_mock.data = {DOMAIN: {}}
    return hass_mock


async def test_async_setup_entry(hass: HomeAssistant, config_entry) -> None:
    """Test async_setup_entry for adding sensors."""
    async_add_entities = MagicMock()

    # Call async_setup_entry to add sensors
    await async_setup_entry(hass, config_entry, async_add_entities)

    # Assert that sensors were added correctly
    assert async_add_entities.call_count == 1
    added_sensors = async_add_entities.call_args[0][0]

    assert len(added_sensors) == 3  # 2 sensors + 1 battery
    assert added_sensors[0].name == "VegeHub Sensor 1"
    assert added_sensors[1].name == "VegeHub Sensor 2"
    assert added_sensors[2].name == "Battery"

    # Check that the sensors are stored in hass.data
    assert added_sensors[0].unique_id in hass.data[DOMAIN]
    assert added_sensors[1].unique_id in hass.data[DOMAIN]
    assert added_sensors[2].unique_id in hass.data[DOMAIN]


def test_vegehub_sensor_properties() -> None:
    """Test VegeHubSensor properties."""
    sensor = VegeHubSensor(
        name="Test Sensor",
        mac_address="1234567890AB",
        slot=1,
        ip_addr="192.168.1.10",
        dev_name="VegeHub1",
        data_type=OPTION_DATA_TYPE_CHOICES[1],
        chan_type="sensor",
    )

    assert sensor.name == "Test Sensor"
    assert sensor.device_class == SensorDeviceClass.MOISTURE
    assert sensor.native_unit_of_measurement == PERCENTAGE
    assert sensor.unique_id == "vegehub_1234567890ab_1"


def test_vh400_transform() -> None:
    """Test VH400_transform function."""
    # Check different ranges of the piecewise function
    assert VH400_transform(0.5) == pytest.approx(4.5454, 0.02)
    assert VH400_transform(1.2) == pytest.approx(12.5, 0.02)
    assert VH400_transform(1.6) == pytest.approx(30.77, 0.05)
    assert VH400_transform(2.0) == pytest.approx(45.45, 0.02)
    assert VH400_transform(2.6) == pytest.approx(75.00, 0.02)
    assert VH400_transform(3.5) == 100.0  # Above max range


def test_native_value() -> None:
    """Test the native_value property for VegeHubSensor."""
    sensor = VegeHubSensor(
        name="Test Sensor",
        mac_address="1234567890AB",
        slot=1,
        ip_addr="192.168.1.10",
        dev_name="VegeHub1",
        data_type=OPTION_DATA_TYPE_CHOICES[2],
        chan_type="sensor",
    )

    # Test with temperature conversion
    sensor._attr_native_value = 1.0
    assert sensor.native_value == pytest.approx(1.0 * 41.67 - 40, 0.01)

    # Test with other data type (voltage)
    sensor._data_type = OPTION_DATA_TYPE_CHOICES[0]
    sensor._attr_native_value = 2.0
    assert sensor.native_value == 2.0

    # Test with percentage conversion
    sensor._data_type = OPTION_DATA_TYPE_CHOICES[1]
    sensor._attr_native_value = 1.5
    assert sensor.native_value == VH400_transform(1.5)


@pytest.mark.asyncio
async def test_async_update_sensor() -> None:
    """Test async_update_sensor method."""
    sensor = VegeHubSensor(
        name="Test Sensor",
        mac_address="1234567890AB",
        slot=1,
        ip_addr="192.168.1.10",
        dev_name="VegeHub1",
        data_type=OPTION_DATA_TYPE_CHOICES[1],
        chan_type="sensor",
    )

    with patch.object(sensor, "async_write_ha_state") as mock_write_ha_state:
        sensor._attr_native_value = 2.0
        await sensor.async_update_sensor(2.0)
        mock_write_ha_state.assert_called_once()
        assert sensor._attr_native_value == 2.0
