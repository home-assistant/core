"""Support for Epion API."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EpionCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key="co2",
        name="CO2",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        key="temperature",
        name="Temperature",
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        key="humidity",
        name="Humidity",
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        key="pressure",
        name="Pressure",
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an Epion entry."""
    coordinator: EpionCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EpionSensor(coordinator, epion_device, description)
        for epion_device in coordinator.data.values()
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class EpionSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Epion Air sensor."""

    def __init__(
        self,
        coordinator: EpionCoordinator,
        epion_device: dict,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize an EpionSensor."""
        super().__init__(coordinator)
        self._epion_coordinator = coordinator
        self._epion_device = epion_device
        self._measurement_key = description.key
        self._display_name = description.name
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_suggested_display_precision = description.suggested_display_precision
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, epion_device["deviceId"])},
            manufacturer="Epion",
            name=epion_device["deviceName"],
        )
        self.unique_id = f"{self._epion_device['deviceId']}_{self._measurement_key}"
        self.has_entity_name = True
        self.name = description.name

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        return self.extract_value()

    @property
    def available(self) -> bool:
        """Return the availability of this sensor."""
        return self.extract_value() is not None

    def extract_value(self) -> float | None:
        """Extract the sensor measurement value from the cached data, or None if it can't be found."""
        my_device_id = self._epion_device["deviceId"]
        if my_device_id not in self._epion_coordinator.data:
            return None  # No data available, this can happen during startup or if the device (temporarily) stopped sending data

        my_device = self._epion_coordinator.data[my_device_id]

        if self._measurement_key not in my_device:
            return None  # No relevant measurement available

        measurement = my_device[self._measurement_key]

        return measurement
