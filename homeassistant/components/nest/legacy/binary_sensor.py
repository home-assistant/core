"""Support for Nest Thermostat binary sensors."""
from itertools import chain
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_MONITORED_CONDITIONS

from . import NestSensorDevice
from .const import DATA_NEST, DATA_NEST_CONFIG

_LOGGER = logging.getLogger(__name__)

BINARY_TYPES = {"online": DEVICE_CLASS_CONNECTIVITY}

CLIMATE_BINARY_TYPES = {
    "fan": None,
    "is_using_emergency_heat": "heat",
    "is_locked": None,
    "has_leaf": None,
}

CAMERA_BINARY_TYPES = {
    "motion_detected": DEVICE_CLASS_MOTION,
    "sound_detected": DEVICE_CLASS_SOUND,
    "person_detected": DEVICE_CLASS_OCCUPANCY,
}

STRUCTURE_BINARY_TYPES = {"away": None}

STRUCTURE_BINARY_STATE_MAP = {"away": {"away": True, "home": False}}

_BINARY_TYPES_DEPRECATED = [
    "hvac_ac_state",
    "hvac_aux_heater_state",
    "hvac_heater_state",
    "hvac_heat_x2_state",
    "hvac_heat_x3_state",
    "hvac_alt_heat_state",
    "hvac_alt_heat_x2_state",
    "hvac_emer_heat_state",
]

_VALID_BINARY_SENSOR_TYPES = {
    **BINARY_TYPES,
    **CLIMATE_BINARY_TYPES,
    **CAMERA_BINARY_TYPES,
    **STRUCTURE_BINARY_TYPES,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nest binary sensors.

    No longer used.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Nest binary sensor based on a config entry."""
    nest = hass.data[DATA_NEST]

    discovery_info = hass.data.get(DATA_NEST_CONFIG, {}).get(CONF_BINARY_SENSORS, {})

    # Add all available binary sensors if no Nest binary sensor config is set
    if discovery_info == {}:
        conditions = _VALID_BINARY_SENSOR_TYPES
    else:
        conditions = discovery_info.get(CONF_MONITORED_CONDITIONS, {})

    for variable in conditions:
        if variable in _BINARY_TYPES_DEPRECATED:
            wstr = (
                f"{variable} is no a longer supported "
                "monitored_conditions. See "
                "https://www.home-assistant.io/integrations/binary_sensor.nest/ "
                "for valid options."
            )
            _LOGGER.error(wstr)

    def get_binary_sensors():
        """Get the Nest binary sensors."""
        sensors = []
        for structure in nest.structures():
            sensors += [
                NestBinarySensor(structure, None, variable)
                for variable in conditions
                if variable in STRUCTURE_BINARY_TYPES
            ]
        device_chain = chain(nest.thermostats(), nest.smoke_co_alarms(), nest.cameras())
        for structure, device in device_chain:
            sensors += [
                NestBinarySensor(structure, device, variable)
                for variable in conditions
                if variable in BINARY_TYPES
            ]
            sensors += [
                NestBinarySensor(structure, device, variable)
                for variable in conditions
                if variable in CLIMATE_BINARY_TYPES and device.is_thermostat
            ]

            if device.is_camera:
                sensors += [
                    NestBinarySensor(structure, device, variable)
                    for variable in conditions
                    if variable in CAMERA_BINARY_TYPES
                ]
                for activity_zone in device.activity_zones:
                    sensors += [
                        NestActivityZoneSensor(structure, device, activity_zone)
                    ]

        return sensors

    async_add_entities(await hass.async_add_executor_job(get_binary_sensors), True)


class NestBinarySensor(NestSensorDevice, BinarySensorEntity):
    """Represents a Nest binary sensor."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return _VALID_BINARY_SENSOR_TYPES.get(self.variable)

    def update(self):
        """Retrieve latest state."""
        value = getattr(self.device, self.variable)
        if self.variable in STRUCTURE_BINARY_TYPES:
            self._state = bool(STRUCTURE_BINARY_STATE_MAP[self.variable].get(value))
        else:
            self._state = bool(value)


class NestActivityZoneSensor(NestBinarySensor):
    """Represents a Nest binary sensor for activity in a zone."""

    def __init__(self, structure, device, zone):
        """Initialize the sensor."""
        super().__init__(structure, device, "")
        self.zone = zone
        self._name = f"{self._name} {self.zone.name} activity"

    @property
    def unique_id(self):
        """Return unique id based on camera serial and zone id."""
        return f"{self.device.serial}-{self.zone.zone_id}"

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return DEVICE_CLASS_MOTION

    def update(self):
        """Retrieve latest state."""
        self._state = self.device.has_ongoing_motion_in_zone(self.zone.zone_id)
