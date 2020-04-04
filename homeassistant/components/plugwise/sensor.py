"""Plugwise Sensor component for Home Assistant."""

import logging
from typing import Dict

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DEVICE_CLASS_GAS, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_TEMPERATURE = [
    "Temperature",
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    "mdi:thermometer",
]
ATTR_BATTERY_LEVEL = ["Charge", "%", DEVICE_CLASS_BATTERY, "mdi:water-battery"]
ATTR_ILLUMINANCE = [
    "Illuminance",
    "lm",
    DEVICE_CLASS_ILLUMINANCE,
    "mdi:lightbulb-on-outline",
]
ATTR_PRESSURE = ["Pressure", PRESSURE_MBAR, DEVICE_CLASS_PRESSURE, "mdi:water"]
SENSOR_MAP = {
    "thermostat": ATTR_TEMPERATURE,
    "temperature": ATTR_TEMPERATURE,
    "battery": ATTR_BATTERY_LEVEL,
    "battery_charge": ATTR_BATTERY_LEVEL,
    "temperature_difference": ATTR_TEMPERATURE,
    "electricity_consumed": [
        "Current Consumed Power",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_produced": [
        "Current Produced Power",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_interval": [
        "Consumed Power Interval",
        "Wh",
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_produced_interval": [
        "Produced Power Interval",
        "Wh",
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "outdoor_temperature": ATTR_TEMPERATURE,
    "illuminance": ATTR_ILLUMINANCE,
    "boiler_temperature": ATTR_TEMPERATURE,
    "electricity_consumed_off_peak_point": [
        "Current Consumed Power (off peak)",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_peak_point": [
        "Current Consumed Power",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:flash",
    ],
    "electricity_consumed_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        "kWh",
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "electricity_consumed_peak_cumulative": [
        "Cumulative Consumed Power",
        "kWh",
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "electricity_produced_off_peak_point": [
        "Current Consumed Power (off peak)",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:white-balance-sunny",
    ],
    "electricity_produced_peak_point": [
        "Current Consumed Power",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:white-balance-sunny",
    ],
    "electricity_produced_off_peak_cumulative": [
        "Cumulative Consumed Power (off peak)",
        "kWh",
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "electricity_produced_peak_cumulative": [
        "Cumulative Consumed Power",
        "kWh",
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
    "gas_consumed_peak_interval": [
        "Current Consumed Gas",
        "m3",
        DEVICE_CLASS_GAS,
        "mdi:gas-cylinder",
    ],
    "gas_consumed_peak_cumulative": [
        "Cumulative Consumed Gas",
        "m3",
        DEVICE_CLASS_GAS,
        "mdi:gauge",
    ],
    "net_electricity_point": [
        "Current net Power",
        "W",
        DEVICE_CLASS_POWER,
        "mdi:solar-power",
    ],
    "net_electricity_cumulative": [
        "Cumulative net Power",
        "kWh",
        DEVICE_CLASS_POWER,
        "mdi:gauge",
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile sensors from a config entry."""
    _LOGGER.debug("Plugwise hass data %s", hass.data[DOMAIN])
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    updater = hass.data[DOMAIN][config_entry.entry_id]["updater"]

    _LOGGER.debug("Plugwise sensor type %s", api.smile_type)

    devices = []
    all_devices = api.get_all_devices()
    _LOGGER.debug("Plugwise all devices (not just sensor) %s", all_devices)
    for dev_id, device in all_devices.items():
        data = api.get_device_data(dev_id)
        _LOGGER.debug("Plugwise all device data (not just sensor) %s", data)
        _LOGGER.debug("Plugwise sensor Dev %s", device["name"])
        for sensor, sensor_type in SENSOR_MAP.items():
            if sensor in data:
                if data[sensor] is not None:
                    if "power" in device["types"]:
                        devices.append(
                            PwPowerSensor(
                                api,
                                updater,
                                "{}_{}".format(device["name"], sensor),
                                dev_id,
                                sensor,
                                sensor_type,
                            )
                        )
                    else:
                        devices.append(
                            PwThermostatSensor(
                                api,
                                updater,
                                "{}_{}".format(device["name"], sensor),
                                dev_id,
                                sensor,
                                sensor_type,
                            )
                        )
                    _LOGGER.info(
                        "Added sensor.%s", "{}_{}".format(device["name"], sensor)
                    )

    async_add_entities(devices, True)


class PwThermostatSensor(Entity):
    """Thermostat (or generic) sensor devices."""

    def __init__(self, api, updater, name, dev_id, sensor, sensor_type):
        """Set up the Plugwise API."""
        self._api = api
        self._updater = updater
        self._name = name
        self._dev_id = dev_id
        self._device = sensor_type[2]
        self._sensor = sensor
        self._sensor_type = sensor_type
        self._unit_of_measurement = sensor_type[1]
        self._icon = sensor_type[3]
        self._class = sensor_type[2]
        self._state = None
        self._unique_id = f"{dev_id}-{name}-{sensor_type[2]}"
        _LOGGER.debug("Registering Plugwise %s", self._unique_id)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._updater.async_add_listener(self._update_callback)

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        self._updater.async_remove_listener(self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.update()
        self.async_write_ha_state()

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._class

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._dev_id)},
            "name": self._name,
            "manufacturer": "Plugwise",
            "via_device": (DOMAIN, self._api.gateway_id),
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon for the sensor."""
        return self._icon

    def update(self):
        """Update the entity."""
        _LOGGER.debug("Update sensor called")
        data = self._api.get_device_data(self._dev_id)

        if data is None:
            _LOGGER.error("Received no data for device %s.", self._name)
        else:
            if self._sensor in data:
                if data[self._sensor] is not None:
                    measurement = data[self._sensor]
                    self._state = measurement


class PwPowerSensor(Entity):
    """Power sensor devices."""

    def __init__(self, api, updater, name, dev_id, sensor, sensor_type):
        """Set up the Plugwise API."""
        self._api = api
        self._updater = updater
        self._name = name
        self._dev_id = dev_id
        self._device = sensor_type[0]
        self._unit_of_measurement = sensor_type[1]
        self._icon = sensor_type[3]
        self._class = sensor_type[2]
        self._sensor = sensor
        self._state = None
        self._unique_id = f"{dev_id}-{name}-{sensor_type[2]}"
        _LOGGER.debug("Registering Plugwise %s", self._unique_id)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._updater.async_add_listener(self._update_callback)

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        self._updater.async_remove_listener(self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.update()
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Update the entity."""
        _LOGGER.debug("Update sensor called")
        data = self._api.get_device_data(self._dev_id)

        if data is None:
            _LOGGER.error("Received no data for device %s.", self._name)
        else:
            if self._sensor in data:
                if data[self._sensor] is not None:
                    measurement = data[self._sensor]
                    if self._unit_of_measurement == "kWh":
                        measurement = int(measurement / 1000)
                    self._state = measurement
