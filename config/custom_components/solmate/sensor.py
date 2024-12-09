"""Sensor platform for solmate integration."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    has: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the sensor platform."""
    async_add_entities(
        [
            MockHomePowerSensor(),
            MockPVProductionSensor(),
            MockBatterySoCSensor(),
            MockFastChargeButton(),
        ]
    )


class MockHomePowerSensor(SensorEntity):
    """Sensor for mocking home power consumption."""

    _attr_name = "Mock Home Power Consumption"
    _attr_unique_id = "mock_home_power_consumption"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._attr_native_value = 1500  # Example fixed value


class MockPVProductionSensor(SensorEntity):
    """Sensor for mocking PV production."""

    _attr_name = "Mock PV Production"
    _attr_unique_id = "mock_pv_production"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._attr_native_value = 3000  # Example fixed value


class MockBatterySoCSensor(SensorEntity):
    """Sensor for mocking battery state of charge."""

    _attr_name = "Mock Battery SoC"
    _attr_unique_id = "mock_battery_soc"
    _attr_native_unit_of_measurement = "%"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._attr_native_value = 75  # Example fixed value


class MockFastChargeButton(BinarySensorEntity):
    """Binary sensor for mocking fast charge button."""

    _attr_name = "Mock Fast Charge Button"
    _attr_unique_id = "mock_fast_charge_button"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self) -> None:
        """Initialize the binary sensor."""
        self._attr_is_on = False
