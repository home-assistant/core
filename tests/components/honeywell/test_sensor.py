"""Test honeywell sensor."""
import asyncio
from unittest.mock import create_autospec

import pytest
from somecomfort import Device

from homeassistant.components.honeywell import HoneywellService
from homeassistant.components.honeywell.const import (
    SENSOR_LOCATION_INDOOR,
    SENSOR_LOCATION_OUTDOOR,
)
from homeassistant.components.honeywell.sensor import HoneywellUSSensor
from homeassistant.const import DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE


@pytest.fixture
def sensor_device():
    """Mock honeywell sensor device."""
    mock_device = create_autospec(Device, instance=True)
    mock_device.name = "device1"
    mock_device.mac_address = "macaddress1"
    return mock_device


@pytest.fixture
def data(sensor_device):
    """Mock honeywell service."""
    mock_data = create_autospec(HoneywellService, instance=True)
    mock_data.device = sensor_device
    return mock_data


async def test_state_no_data(data):
    """Test device has no sensors."""
    sensor = HoneywellUSSensor(data, "", "")
    assert sensor.state is None


async def test_indoor_temperature(sensor_device, data):
    """Test indoor temperature sensor."""
    sensor_device.current_temperature = 20
    sensor = HoneywellUSSensor(data, SENSOR_LOCATION_INDOOR, DEVICE_CLASS_TEMPERATURE)
    assert sensor.state == 20


async def test_indoor_humidity(sensor_device, data):
    """Test indoor humidity sensor."""
    sensor_device.current_humidity = 40
    sensor = HoneywellUSSensor(data, SENSOR_LOCATION_INDOOR, DEVICE_CLASS_HUMIDITY)
    assert sensor.state == 40


async def test_outdoor_temperature(sensor_device, data):
    """Test outdoor temperature sensor."""
    sensor_device.outdoor_temperature = 5
    sensor = HoneywellUSSensor(data, SENSOR_LOCATION_OUTDOOR, DEVICE_CLASS_TEMPERATURE)
    assert sensor.state == 5


async def test_outdoor_humidity(sensor_device, data):
    """Test outdoor humidity sensor."""
    sensor_device.outdoor_humidity = 25
    sensor = HoneywellUSSensor(data, SENSOR_LOCATION_OUTDOOR, DEVICE_CLASS_HUMIDITY)
    assert sensor.state == 25


async def test_sensor_update(data):
    """Test updating data."""
    data.update.return_value = asyncio.Future()
    data.update.return_value.set_result(None)
    sensor = HoneywellUSSensor(data, SENSOR_LOCATION_INDOOR, DEVICE_CLASS_TEMPERATURE)
    await sensor.async_update()
    data.update.assert_called_once()
