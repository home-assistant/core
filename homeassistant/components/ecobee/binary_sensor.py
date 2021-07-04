"""Support for Ecobee binary sensors."""
from typing import Any

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER


async def async_setup_entry(hass, config_entry, async_add_entities):
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

    _attr_device_class = DEVICE_CLASS_OCCUPANCY

    def __init__(self, data, sensor_name, sensor_index):
        """Initialize the Ecobee sensor."""
        self.data = data
        name = f"{sensor_name} Occupancy"
        self._attr_name = name.rstrip()
        self.sensor_name = sensor_name
        self.index = sensor_index
        self._state = None
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                if "code" in sensor:
                    self._attr_unique_id = f"{sensor['code']}-{self.device_class}"
                thermostat = self.data.ecobee.get_thermostat(self.index)
                self._attr_unique_id = (
                    f"{thermostat['identifier']}-{sensor['id']}-{self.device_class}"
                )
        self._attr_available = self.data.ecobee.get_thermostat(self.index)["runtime"][
            "connected"
        ]
        self._attr_is_on = self._state == "true"

    @property
    def device_info(self) -> Any:
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
            return {
                "identifiers": {(DOMAIN, identifier)},
                "name": self.sensor_name,
                "manufacturer": MANUFACTURER,
                "model": model,
            }
        return None

    async def async_update(self):
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
