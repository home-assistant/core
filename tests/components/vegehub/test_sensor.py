"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.vegehub.sensor import VegeHubSensor, async_setup_entry
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant

TEST_API_KEY = "1234567890ABCD"
TEST_SERVER = "http://example.com"


async def test_async_setup_entry(hass: HomeAssistant, config_entry) -> None:
    """Test async_setup_entry for adding sensors."""
    async_add_entities = MagicMock()

    await config_entry.runtime_data.hub.setup(TEST_API_KEY, TEST_SERVER)

    # Call async_setup_entry to add sensors
    await async_setup_entry(hass, config_entry, async_add_entities)

    # Assert that sensors were added correctly
    assert async_add_entities.call_count == 1
    added_sensors = async_add_entities.call_args[0][0]

    assert len(added_sensors) == 5  # 2 sensors + 2 actuators + 1 battery


def test_vegehub_sensor_properties() -> None:
    """Test VegeHubSensor properties."""
    sensor = VegeHubSensor(
        mac_address="1234567890AB",
        slot=1,
        dev_name="VegeHub1",
    )

    assert sensor.device_class == SensorDeviceClass.VOLTAGE
    assert sensor.native_unit_of_measurement == UnitOfElectricPotential.VOLT
    assert sensor.unique_id == "vegehub_1234567890ab_1"


def test_native_value() -> None:
    """Test the native_value property for VegeHubSensor."""
    sensor = VegeHubSensor(
        mac_address="1234567890AB",
        slot=1,
        dev_name="VegeHub1",
    )

    # Test with other data type (voltage)
    sensor._attr_native_value = 2.0
    assert sensor.native_value == 2.0


@pytest.mark.asyncio
async def test_async_update_sensor() -> None:
    """Test async_update_sensor method."""
    sensor = VegeHubSensor(
        mac_address="1234567890AB",
        slot=1,
        dev_name="VegeHub1",
    )

    with patch.object(sensor, "async_write_ha_state") as mock_write_ha_state:
        sensor._attr_native_value = 2.0
        await sensor.async_update_sensor(2.0)
        mock_write_ha_state.assert_called_once()
        assert sensor._attr_native_value == 2.0
