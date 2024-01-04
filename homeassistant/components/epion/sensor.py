"""Support for Epion API."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_API_CLIENT, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an Epion entry."""
    epion_base = hass.data[DOMAIN][entry.entry_id][DATA_API_CLIENT]

    entities = []
    current_data = epion_base.last_response
    for epion_device in current_data["devices"]:
        # Relevant keys are: deviceId, deviceName, locationId, lastMeasurement, co2, temperature, humidity, pressure
        entities.append(EpionSensor(epion_base, epion_device, "co2", hass))
        entities.append(EpionSensor(epion_base, epion_device, "temperature", hass))
        entities.append(EpionSensor(epion_base, epion_device, "humidity", hass))
        entities.append(EpionSensor(epion_base, epion_device, "pressure", hass))

    async_add_entities(entities)


class EpionSensor(SensorEntity):
    """Representation of an Epion Air sensor."""

    def __init__(self, epion_base, epion_device, key, hass) -> None:
        """Initialize an EpionSensor."""
        self._epion_base = epion_base
        self._epion_device = epion_device
        self._measurement_key = key
        self._last_value: float | None = self.extract_value()
        self._display_name = ""
        if key == "temperature":
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._display_name = "Temperature"
        elif key == "humidity":
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._display_name = "Humidity"
        elif key == "pressure":
            self._attr_native_unit_of_measurement = UnitOfPressure.HPA
            self._attr_device_class = SensorDeviceClass.ATMOSPHERIC_PRESSURE
            self._display_name = "Pressure"
        else:
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
            self._attr_device_class = SensorDeviceClass.CO2
            self._display_name = "CO2"

        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, epion_device["deviceId"])},
            manufacturer="Epion",
            name=epion_device["deviceName"],
        )
        self.entity_id = generate_entity_id(
            "sensor.{}", f"{epion_device['deviceId']}_{key}", hass=hass
        )

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return f"{self._epion_device['deviceId']}_{self._measurement_key}"

    @property
    def name(self):
        my_device_id = self._epion_device["deviceId"]
        device_name = "Unknown"

        if my_device_id not in self._epion_base.device_data:
            device_name = self._epion_device.get("deviceName", my_device_id)
        else:
            my_device = self._epion_base.device_data[my_device_id]
            device_name = my_device["deviceName"]
        return f"{device_name} {self._display_name}"

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        if self._last_value is not None:
            return round(self._last_value, 1)
        return None

    @property
    def available(self) -> bool:
        return self._last_value is not None

    def extract_value(self) -> float | None:
        """Extract the sensor measurement value from the cached data, or None if it can't be found."""
        my_device_id = self._epion_device["deviceId"]
        if my_device_id not in self._epion_base.device_data:
            return None  # No data available, this can happen during startup or if the device (temporarily) stopped sending data

        my_device = self._epion_base.device_data[my_device_id]

        if self._measurement_key not in my_device:
            return None  # No relevant measurement available

        measurement = my_device[self._measurement_key]

        return measurement

    async def async_update(self) -> None:
        """Get the latest data from the Epion API and update the state."""
        await self._epion_base.async_update()
        self._last_value = self.extract_value()
