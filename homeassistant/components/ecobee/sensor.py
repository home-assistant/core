"""Support for Ecobee sensors."""
from datetime import datetime

from pyecobee.const import ECOBEE_STATE_CALIBRATING, ECOBEE_STATE_UNKNOWN

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from .const import _LOGGER, DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER
from .util import safe_list_get

SENSOR_TYPES = {
    "temperature": ["Temperature", TEMP_FAHRENHEIT],
    "humidity": ["Humidity", UNIT_PERCENTAGE],
}
NOTIFICATIONS_KEY = "Notifications"


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

        if "notificationSettings" in data.ecobee.thermostats[index]:
            dev.append(
                EcobeeSensor(
                    data,
                    data.ecobee.thermostats[index]["name"],
                    NOTIFICATIONS_KEY,
                    index,
                    data.ecobee.get_equipment_notifications(index),
                )
            )

    async_add_entities(dev, True)


class EcobeeSensor(Entity):
    """Representation of an Ecobee sensor."""

    def __init__(self, data, sensor_name, sensor_type, sensor_index, attributes=None):
        """Initialize the sensor."""
        self.data = data
        self._name = f"{sensor_name} {safe_list_get(SENSOR_TYPES, sensor_type, [sensor_type, None])[0]}"
        self.sensor_name = sensor_name
        self.type = sensor_type
        self.index = sensor_index
        self._state = None
        self._unit_of_measurement = safe_list_get(
            SENSOR_TYPES, sensor_type, [None, None]
        )[1]
        self._attributes = attributes

        _LOGGER.debug(
            "SenserName:%s",
            f"{sensor_name} {safe_list_get(SENSOR_TYPES, sensor_type, [sensor_type, None])[0]}",
        )

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name

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
    def device_info(self):
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
                    _LOGGER.error(
                        "Model number for ecobee thermostat %s not recognized. "
                        "Please visit this link and provide the following information: "
                        "https://github.com/home-assistant/home-assistant/issues/27172 "
                        "Unrecognized model number: %s",
                        thermostat["name"],
                        thermostat["modelNumber"],
                    )
            break

        if identifier is not None and model is not None:
            return {
                "identifiers": {(DOMAIN, identifier)},
                "name": self.sensor_name,
                "manufacturer": MANUFACTURER,
                "model": model,
            }
        return None

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.type in (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE):
            return self.type
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state in [ECOBEE_STATE_CALIBRATING, ECOBEE_STATE_UNKNOWN, "unknown"]:
            return None

        if self.type == "temperature":
            return float(self._state) / 10

        if self.type == NOTIFICATIONS_KEY:
            return len(
                [
                    notification
                    for notification in self._attributes
                    if notification["enabled"]
                    and datetime.strptime(notification["remindMeDate"], "%Y-%m-%d")
                    <= datetime.now()
                ]
            )

        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def state_attributes(self):
        """Return the attributes of the sensor."""
        if self.type != NOTIFICATIONS_KEY:
            return None

        if self._attributes is None:
            self._attributes = {}
        else:
            self._attributes = {
                NOTIFICATIONS_KEY: [
                    notification
                    for notification in self._attributes
                    if notification["enabled"]
                ]
            }

        return self._attributes

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != self.type:
                    continue
                self._state = item["value"]
                break
