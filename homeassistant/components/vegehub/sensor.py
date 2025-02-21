"""Sensor configuration for VegeHub integration."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, UnitOfElectricPotential
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import VegeHubCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vegetronix sensors from a config entry."""
    sensors: list[VegeHubSensor] = []
    hub = config_entry.runtime_data.hub

    # We add up the number of sensors, plus the number of actuators, then add one
    # for battery reading, and one because the array is 1 based instead of 0 based.
    for i in range(hub.num_sensors + hub.num_actuators + 1):  # Add 1 for battery
        sensor = VegeHubSensor(
            index=i + 1,
            coordinator=config_entry.runtime_data.coordinator,
        )
        sensors.append(sensor)

    async_add_entities(sensors)


class VegeHubSensor(CoordinatorEntity[VegeHubCoordinator], SensorEntity):
    """Class for VegeHub Analog Sensors."""

    _attr_has_entity_name = True
    _attr_translation_key = "analog_sensor"
    _unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_suggested_unit_of_measurement = _unit_of_measurement
    _attr_native_unit_of_measurement = _unit_of_measurement
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        index: int,
        coordinator: VegeHubCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        config_entry = coordinator.config_entry

        # This is needed for mypy to understand that config_entry is not None
        if config_entry is None:
            raise ValueError("Config entry should never be None for VegeHubSensor")

        self._attr_translation_placeholders = {"index": str(index)}
        self._attr_available = False
        self._mac_address = config_entry.data[CONF_MAC]
        self._attr_unique_id = (
            f"{self._mac_address}_{index}".lower()
        )  # Generate a unique_id using mac and slot
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac_address)},
            name=config_entry.data[CONF_HOST],
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.coordinator.data is not None
            and self._attr_unique_id is not None
            and self._attr_unique_id in self.coordinator.data
        ):
            self._attr_native_value = self.coordinator.data[self._attr_unique_id]
        super()._handle_coordinator_update()
