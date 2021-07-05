"""Support for Ecobee sensors."""
from pyecobee.const import ECOBEE_STATE_CALIBRATING, ECOBEE_STATE_UNKNOWN

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_FAHRENHEIT,
)

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

SENSOR_TYPES = {
    "temperature": ["Temperature", TEMP_FAHRENHEIT],
    "humidity": ["Humidity", PERCENTAGE],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up ecobee (temperature and humidity) sensors."""
    data = hass.data[DOMAIN]
    dev = []
    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                if item["type"] not in ("temperature", "humidity"):
                    continue

                dev.append(EcobeeSensor(data, sensor["name"], item["type"], index))

    async_add_entities(dev, True)


class EcobeeSensor(SensorEntity):
    """Representation of an Ecobee sensor."""

    def __init__(self, data, sensor_name, sensor_type, sensor_index):
        """Initialize the sensor."""
        self.data = data
        self._attr_name = f"{sensor_name} {SENSOR_TYPES[sensor_type][0]}"
        self.sensor_name = sensor_name
        self.type = sensor_type
        self.index = sensor_index
        self._attr_unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                if "code" in sensor:
                    self._attr_unique_id = f"{sensor['code']}-{self.device_class}"
                else:
                    self._attr_unique_id = f"{self.data.ecobee.get_thermostat(self.index)['identifier']}-{sensor['id']}-{self.device_class}"
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            if "code" in sensor:
                identifier = sensor["code"]
                model = "ecobee Room Sensor"
            else:
                thermostat = self.data.ecobee.get_thermostat(self.index)
                identifier = thermostat["identifier"]
                model = (
                    f"{ECOBEE_MODEL_TO_NAME.get(thermostat['modelNumber'])} Thermostat"
                )
            break

        if identifier is not None and model is not None:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, identifier)},
                "name": self.sensor_name,
                "manufacturer": MANUFACTURER,
                "model": model,
            }
        self._attr_device_class = (
            self.type
            if self.type in (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE)
            else None
        )

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.data.update()
        self._attr_available = self.data.ecobee.get_thermostat(self.index)["runtime"][
            "connected"
        ]
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != self.type:
                    continue
                self._attr_state = item["value"]
                if self._attr_state in [
                    ECOBEE_STATE_CALIBRATING,
                    ECOBEE_STATE_UNKNOWN,
                    "unknown",
                ]:
                    self._attr_state = None
                elif self.type == "temperature":
                    self._attr_state = float(self._attr_state) / 10
                break
