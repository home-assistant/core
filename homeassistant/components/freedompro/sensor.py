"""Support for Freedompro sensor."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

DEVICE_CLASS_MAP = {
    "temperatureSensor": SensorDeviceClass.TEMPERATURE,
    "humiditySensor": SensorDeviceClass.HUMIDITY,
    "lightSensor": SensorDeviceClass.ILLUMINANCE,
}
STATE_CLASS_MAP = {
    "temperatureSensor": SensorStateClass.MEASUREMENT,
    "humiditySensor": SensorStateClass.MEASUREMENT,
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            manufacturer="Freedompro",
            model=device["type"],
            name=self.name,
        )
        self._attr_device_class = DEVICE_CLASS_MAP[device["type"]]
        self._attr_state_class = STATE_CLASS_MAP[device["type"]]
        self._attr_native_unit_of_measurement = UNIT_MAP[device["type"]]
        self._attr_native_value = 0

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
            self._attr_native_value = state[DEVICE_KEY_MAP[self._type]]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
