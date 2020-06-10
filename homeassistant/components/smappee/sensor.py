"""Support for monitoring a Smappee energy sensor."""
from datetime import timedelta
import logging

from homeassistant.const import (
    DEGREE,
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    UNIT_PERCENTAGE,
    VOLT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers.entity import Entity

from . import DATA_SMAPPEE

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = "Smappee"
SENSOR_TYPES = {
    "solar": ["Solar", "mdi:white-balance-sunny", "local", POWER_WATT, "solar"],
    "active_power": [
        "Active Power",
        "mdi:power-plug",
        "local",
        POWER_WATT,
        "active_power",
    ],
    "current": ["Current", "mdi:gauge", "local", ELECTRICAL_CURRENT_AMPERE, "current"],
    "voltage": ["Voltage", "mdi:gauge", "local", VOLT, "voltage"],
    "active_cosfi": [
        "Power Factor",
        "mdi:gauge",
        "local",
        UNIT_PERCENTAGE,
        "active_cosfi",
    ],
    "alwayson_today": [
        "Always On Today",
        "mdi:gauge",
        "remote",
        ENERGY_KILO_WATT_HOUR,
        "alwaysOn",
    ],
    "solar_today": [
        "Solar Today",
        "mdi:white-balance-sunny",
        "remote",
        ENERGY_KILO_WATT_HOUR,
        "solar",
    ],
    "power_today": [
        "Power Today",
        "mdi:power-plug",
        "remote",
        ENERGY_KILO_WATT_HOUR,
        "consumption",
    ],
    "water_sensor_1": [
        "Water Sensor 1",
        "mdi:water",
        "water",
        VOLUME_CUBIC_METERS,
        "value1",
    ],
    "water_sensor_2": [
        "Water Sensor 2",
        "mdi:water",
        "water",
        VOLUME_CUBIC_METERS,
        "value2",
    ],
    "water_sensor_temperature": [
        "Water Sensor Temperature",
        "mdi:temperature-celsius",
        "water",
        DEGREE,
        "temperature",
    ],
    "water_sensor_humidity": [
        "Water Sensor Humidity",
        "mdi:water-percent",
        "water",
        UNIT_PERCENTAGE,
        "humidity",
    ],
    "water_sensor_battery": [
        "Water Sensor Battery",
        "mdi:battery",
        "water",
        UNIT_PERCENTAGE,
        "battery",
    ],
}

SCAN_INTERVAL = timedelta(seconds=30)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Smappee sensor."""
    smappee = hass.data[DATA_SMAPPEE]

    dev = []
    if smappee.is_remote_active:
        for location_id in smappee.locations.keys():
            for sensor in SENSOR_TYPES:
                if "remote" in SENSOR_TYPES[sensor]:
                    dev.append(
                        SmappeeSensor(
                            smappee, location_id, sensor, SENSOR_TYPES[sensor]
                        )
                    )
                elif "water" in SENSOR_TYPES[sensor]:
                    for items in smappee.info[location_id].get("sensors"):
                        dev.append(
                            SmappeeSensor(
                                smappee,
                                location_id,
                                "{}:{}".format(sensor, items.get("id")),
                                SENSOR_TYPES[sensor],
                            )
                        )

    if smappee.is_local_active:
        if smappee.is_remote_active:
            location_keys = smappee.locations.keys()
        else:
            location_keys = [None]
        for location_id in location_keys:
            for sensor in SENSOR_TYPES:
                if "local" in SENSOR_TYPES[sensor]:
                    dev.append(
                        SmappeeSensor(
                            smappee, location_id, sensor, SENSOR_TYPES[sensor]
                        )
                    )

    add_entities(dev, True)


class SmappeeSensor(Entity):
    """Implementation of a Smappee sensor."""

    def __init__(self, smappee, location_id, sensor, attributes):
        """Initialize the Smappee sensor."""
        self._smappee = smappee
        self._location_id = location_id
        self._attributes = attributes
        self._sensor = sensor
        self.data = None
        self._state = None
        self._name = self._attributes[0]
        self._icon = self._attributes[1]
        self._type = self._attributes[2]
        self._unit_of_measurement = self._attributes[3]
        self._smappe_name = self._attributes[4]

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._location_id:
            location_name = self._smappee.locations[self._location_id]
        else:
            location_name = "Local"

        return f"{SENSOR_PREFIX} {location_name} {self._name}"

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self._location_id:
            attr["Location Id"] = self._location_id
            attr["Location Name"] = self._smappee.locations[self._location_id]
        return attr

    def update(self):
        """Get the latest data from Smappee and update the state."""
        self._smappee.update()

        if self._sensor in ["alwayson_today", "solar_today", "power_today"]:
            data = self._smappee.consumption[self._location_id]
            if data:
                consumption = data.get("consumptions")[-1]
                _LOGGER.debug("%s %s", self._sensor, consumption)
                value = consumption.get(self._smappe_name)
                self._state = round(value / 1000, 2)
        elif self._sensor == "active_cosfi":
            cosfi = self._smappee.active_cosfi()
            _LOGGER.debug("%s %s", self._sensor, cosfi)
            if cosfi:
                self._state = round(cosfi, 2)
        elif self._sensor == "current":
            current = self._smappee.active_current()
            _LOGGER.debug("%s %s", self._sensor, current)
            if current:
                self._state = round(current, 2)
        elif self._sensor == "voltage":
            voltage = self._smappee.active_voltage()
            _LOGGER.debug("%s %s", self._sensor, voltage)
            if voltage:
                self._state = round(voltage, 3)
        elif self._sensor == "active_power":
            data = self._smappee.instantaneous
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                value1 = [
                    float(i["value"])
                    for i in data
                    if i["key"].endswith("phase0ActivePower")
                ]
                value2 = [
                    float(i["value"])
                    for i in data
                    if i["key"].endswith("phase1ActivePower")
                ]
                value3 = [
                    float(i["value"])
                    for i in data
                    if i["key"].endswith("phase2ActivePower")
                ]
                active_power = sum(value1 + value2 + value3) / 1000
                self._state = round(active_power, 2)
        elif self._sensor == "solar":
            data = self._smappee.instantaneous
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                value1 = [
                    float(i["value"])
                    for i in data
                    if i["key"].endswith("phase3ActivePower")
                ]
                value2 = [
                    float(i["value"])
                    for i in data
                    if i["key"].endswith("phase4ActivePower")
                ]
                value3 = [
                    float(i["value"])
                    for i in data
                    if i["key"].endswith("phase5ActivePower")
                ]
                power = sum(value1 + value2 + value3) / 1000
                self._state = round(power, 2)
        elif self._type == "water":
            sensor_name, sensor_id = self._sensor.split(":")
            data = self._smappee.sensor_consumption[self._location_id].get(
                int(sensor_id)
            )
            if data:
                tempdata = data.get("records")
                if tempdata:
                    consumption = tempdata[-1]
                    _LOGGER.debug("%s (%s) %s", sensor_name, sensor_id, consumption)
                    value = consumption.get(self._smappe_name)
                    self._state = value
