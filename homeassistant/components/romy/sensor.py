"""Sensor checking adc and status values from your ROMY."""

from romy import RomyRobot

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import RomyVacuumCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    romy_status_sensor_entitiy_battery = RomyStatusSensor(
        coordinator,
        coordinator.romy,
        SensorDeviceClass.BATTERY,
        "Battery Level",
        "battery_level",
        PERCENTAGE,
    )
    romy_status_sensor_entitiy_rssi = RomyStatusSensor(
        coordinator,
        coordinator.romy,
        SensorDeviceClass.SIGNAL_STRENGTH,
        "RSSI Level",
        "rssi",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    )

    # add status sensors
    romy_status_sensor_entities = [
        romy_status_sensor_entitiy_battery,
        romy_status_sensor_entitiy_rssi,
    ]
    async_add_entities(romy_status_sensor_entities, True)

    adc_sensor_entities = []
    romy_adc_sensor_entitiy_dustbin_full = RomyAdcSensor(
        coordinator, coordinator.romy, "Dustbin Full Level", "dustbin_sensor"
    )

    # add dustbin sensor if present
    if "dustbin_sensor" in coordinator.romy.adc_sensors:
        LOGGER.info("Dustbin Sensor found for ROMY %s", coordinator.romy.unique_id)
        adc_sensor_entities.append(romy_adc_sensor_entitiy_dustbin_full)

    async_add_entities(adc_sensor_entities, True)


class RomyStatusSensor(CoordinatorEntity[RomyVacuumCoordinator], SensorEntity):
    """RomyStatusSensor Class."""

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
        device_class: SensorDeviceClass,
        sensor_name: str,
        sensor_descriptor: str,
        measurement_unit: str,
    ) -> None:
        """Initialize ROMYs StatusSensor."""
        self._sensor_value: int | None = None
        super().__init__(coordinator)
        self.romy = romy
        self._attr_unique_id = self.romy.unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, romy.unique_id)},
            manufacturer="ROMY",
            name=romy.name,
            model=romy.model,
        )
        self._device_class = device_class
        self._sensor_name = sensor_name
        self._sensor_descriptor = sensor_descriptor
        self._measurement_unit = measurement_unit

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self._sensor_descriptor}_{self._attr_unique_id}"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.DIAGNOSTIC

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit_of_measurement of the device."""
        return self._measurement_unit

    async def async_update(self) -> None:
        """Fetch the sensor value from the device."""
        self._sensor_value = self.romy.sensors[self._sensor_descriptor]

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        return self._sensor_value


class RomyAdcSensor(CoordinatorEntity[RomyVacuumCoordinator], SensorEntity):
    """RomyAdcSensor Class."""

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
        sensor_name: str,
        sensor_descriptor: str,
    ) -> None:
        """Initialize ROMYs DustbinFullSensor."""
        self._sensor_value: int | None = None
        super().__init__(coordinator)
        self.romy = romy
        self._attr_unique_id = self.romy.unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, romy.unique_id)},
            manufacturer="ROMY",
            name=romy.name,
            model=romy.model,
        )
        self._sensor_name = sensor_name
        self._sensor_descriptor = sensor_descriptor

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self._sensor_descriptor}_{self._attr_unique_id}"

    @property
    def entity_category(self) -> EntityCategory:
        """Device entity category."""
        return EntityCategory.DIAGNOSTIC

    async def async_update(self) -> None:
        """Fetch adc value from the device."""
        self._sensor_value = self.romy.adc_sensors[self._sensor_descriptor]

    @property
    def native_value(self) -> int | None:
        """Return the adc value of the sensor."""
        return self._sensor_value
