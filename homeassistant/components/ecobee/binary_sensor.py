"""Support for Ecobee binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ecobee binary (occupancy) sensors."""
    data = hass.data[DOMAIN]
    dev = []
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue

                dev.append(EcobeeBinarySensor(data, sensor["name"], index))

    async_add_entities(dev, True)


class EcobeeBinarySensor(BinarySensorEntity):
    """Representation of an Ecobee sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True

    def __init__(self, data, sensor_name, sensor_index):
        """Initialize the Ecobee sensor."""
        self.data = data
        self.sensor_name = sensor_name.rstrip()
        self.index = sensor_index
        self._state = None

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                if "code" in sensor:
                    return f"{sensor['code']}-{self.device_class}"
                thermostat = self.data.ecobee.get_thermostat(self.index)
                return f"{thermostat['identifier']}-{sensor['id']}-{self.device_class}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""
        identifier = None
        model = None
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            if "code" in sensor:
                identifier = sensor["code"]
                model = "ecobee Room Sensor"
            else:
                thermostat = self.data.ecobee.get_thermostat(self.index)
                identifier = thermostat["identifier"]
                try:
                    model = (
                        f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
                    )
                except KeyError:
                    # Ecobee model is not in our list
                    model = None
            break

        if identifier is not None:
            return DeviceInfo(
                identifiers={(DOMAIN, identifier)},
                manufacturer=MANUFACTURER,
                model=model,
                name=self.sensor_name,
            )
        return None

    @property
    def available(self) -> bool:
        """Return true if device is available."""
        thermostat = self.data.ecobee.get_thermostat(self.index)
        return thermostat["runtime"]["connected"]

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == "true"

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue
                self._state = item["value"]
                break
