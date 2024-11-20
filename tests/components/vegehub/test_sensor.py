"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import MagicMock, patch

import pytest
from vegehub import vh400_transform

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.vegehub.const import DOMAIN, OPTION_DATA_TYPE_CHOICES
from homeassistant.components.vegehub.sensor import VegeHubSensor, async_setup_entry
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


def test_vegehub_sensor_properties() -> None:
    """Test VegeHubSensor properties."""
    sensor = VegeHubSensor(
        mac_address="1234567890AB",
        slot=1,
        ip_addr="192.168.1.10",
        dev_name="VegeHub1",
        data_type=OPTION_DATA_TYPE_CHOICES[1],
        chan_type="sensor",
    )

    assert sensor.device_class == SensorDeviceClass.MOISTURE
    assert sensor.native_unit_of_measurement == PERCENTAGE
    assert sensor.unique_id == "vegehub_1234567890ab_1"


def test_native_value() -> None:
    """Test the native_value property for VegeHubSensor."""
    sensor = VegeHubSensor(
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
    assert sensor.native_value == vh400_transform(1.5)


@pytest.mark.asyncio
async def test_async_update_sensor() -> None:
    """Test async_update_sensor method."""
    sensor = VegeHubSensor(
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
