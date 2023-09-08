"""Support for EyeOnWater sensors."""
import logging
from typing import Any

from pyonwater import DataPoint, Meter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DATA_COORDINATOR, DATA_SMART_METER, DOMAIN, WATER_METER_NAME

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.StreamHandler())


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EyeOnWater sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    meters = hass.data[DOMAIN][config_entry.entry_id][DATA_SMART_METER].meters

    sensors: list [Entity] = []
    for meter in meters:
        sensors.append(EyeOnWaterSensor(meter, coordinator))
        sensors.append(EyeOnWaterTempSensor(meter, coordinator))

    async_add_entities(sensors, update_before_add=False)


class EyeOnWaterTempSensor(CoordinatorEntity, SensorEntity):
    """Representation of an EyeOnWater temperature sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.meter = meter
        self._attr_unique_id = f"{self.meter.meter_uuid}_temperature"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.meter.meter_uuid)},
            name=f"{WATER_METER_NAME} {self.meter.meter_id}",
            model=self.meter.meter_info.reading.model,
            manufacturer=self.meter.meter_info.reading.customer_name,
            hw_version=self.meter.meter_info.reading.hardware_version,
            sw_version=self.meter.meter_info.reading.firmware_version,
        )

    @property
    def native_value(self) -> float | None:
        """Get native value."""
        return self.meter.meter_info.sensors.endpoint_temperature.seven_day_min


class EyeOnWaterSensor(CoordinatorEntity, SensorEntity):
    """Representation of an EyeOnWater sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.meter = meter
        self._state: DataPoint | None = None
        self._available = False

        self._attr_unique_id = meter.meter_uuid
        self._attr_native_unit_of_measurement = meter.native_unit_of_measurement
        self._attr_suggested_display_precision = 0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.meter.meter_uuid)},
            name=f"{WATER_METER_NAME} {self.meter.meter_id}",
            model=self.meter.meter_info.reading.model,
            manufacturer=self.meter.meter_info.reading.customer_name,
            hw_version=self.meter.meter_info.reading.hardware_version,
            sw_version=self.meter.meter_info.reading.firmware_version,
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def native_value(self):
        """Get the latest reading."""
        return self._state.reading

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        return self.meter.meter_info.reading.dict()

    @callback
    def _state_update(self):
        """Call when the coordinator has an update."""
        self._available = self.coordinator.last_update_success
        if self._available:
            self._state = self.meter.reading
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self._state_update))

        if self.coordinator.last_update_success:
            return

        if last_state := await self.async_get_last_state():
            self._state = last_state.state
            self._available = True
