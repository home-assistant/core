"""Support for Freedompro sensor."""
from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DEVICE_CLASS_MAP = {
    "temperatureSensor": DEVICE_CLASS_TEMPERATURE,
    "humiditySensor": DEVICE_CLASS_HUMIDITY,
    "lightSensor": DEVICE_CLASS_ILLUMINANCE,
}
STATE_CLASS_MAP = {
    "temperatureSensor": STATE_CLASS_MEASUREMENT,
    "humiditySensor": STATE_CLASS_MEASUREMENT,
    "lightSensor": None,
}
UNIT_MAP = {
    "temperatureSensor": TEMP_CELSIUS,
    "humiditySensor": PERCENTAGE,
    "lightSensor": LIGHT_LUX,
}
DEVICE_KEY_MAP = {
    "temperatureSensor": "currentTemperature",
    "humiditySensor": "currentRelativeHumidity",
    "lightSensor": "currentAmbientLightLevel",
}
SUPPORTED_SENSORS = {"temperatureSensor", "humiditySensor", "lightSensor"}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Freedompro sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(device, coordinator)
        for device in coordinator.data
        if device["type"] in SUPPORTED_SENSORS
    )


class Device(CoordinatorEntity, SensorEntity):
    """Representation of an Freedompro sensor."""

    def __init__(self, device, coordinator):
        """Initialize the Freedompro sensor."""
        super().__init__(coordinator)
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._type = device["type"]
        self._attr_device_info = {
            "name": self.name,
            "identifiers": {
                (DOMAIN, self.unique_id),
            },
            "model": device["type"],
            "manufacturer": "Freedompro",
        }
        self._attr_device_class = DEVICE_CLASS_MAP[device["type"]]
        self._attr_state_class = STATE_CLASS_MAP[device["type"]]
        self._attr_unit_of_measurement = UNIT_MAP[device["type"]]
        self._attr_state = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self.unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            self._attr_state = state[DEVICE_KEY_MAP[self._type]]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
