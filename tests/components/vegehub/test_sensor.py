"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import MagicMock

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


def test_vegehub_sensor_properties(config_entry) -> None:
    """Test VegeHubSensor properties."""
    sensor = VegeHubSensor(
        mac_address="1234567890AB",
        slot=1,
        dev_name="VegeHub1",
        coordinator=config_entry.runtime_data.coordinator,
    )

    assert sensor.device_class == SensorDeviceClass.VOLTAGE
    assert sensor.native_unit_of_measurement == UnitOfElectricPotential.VOLT
    assert sensor.unique_id == "1234567890ab_1"
