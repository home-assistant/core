"""
Support for getting the state of a Thermoworks Smoke Thermometer.

Requires Smoke Gateway Wifi with an internet connection.
"""
from __future__ import annotations

import logging

from requests import RequestException
from requests.exceptions import HTTPError
from stringcase import camelcase, snakecase
import thermoworks_smoke
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_EMAIL,
    CONF_EXCLUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

PROBE_1 = "probe1"
PROBE_2 = "probe2"
PROBE_1_MIN = "probe1_min"
PROBE_1_MAX = "probe1_max"
PROBE_2_MIN = "probe2_min"
PROBE_2_MAX = "probe2_max"
BATTERY_LEVEL = "battery"
FIRMWARE = "firmware"

SERIAL_REGEX = "^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$"

# map types to labels
SENSOR_TYPES = {
    PROBE_1: "Probe 1",
    PROBE_2: "Probe 2",
    PROBE_1_MIN: "Probe 1 Min",
    PROBE_1_MAX: "Probe 1 Max",
    PROBE_2_MIN: "Probe 2 Min",
    PROBE_2_MAX: "Probe 2 Max",
}

# exclude these keys from thermoworks data
EXCLUDE_KEYS = [FIRMWARE]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[PROBE_1, PROBE_2]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
            cv.ensure_list, [cv.matches_regex(SERIAL_REGEX)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the thermoworks sensor."""

    email = config[CONF_EMAIL]
    password = config[CONF_PASSWORD]
    monitored_variables = config[CONF_MONITORED_CONDITIONS]
    excluded = config[CONF_EXCLUDE]

    try:
        mgr = thermoworks_smoke.initialize_app(email, password, True, excluded)

        # list of sensor devices
        dev = []

        # get list of registered devices
        for serial in mgr.serials():
            for variable in monitored_variables:
                dev.append(ThermoworksSmokeSensor(variable, serial, mgr))

        add_entities(dev, True)
    except HTTPError as error:
        msg = f"{error.strerror}"
        if "EMAIL_NOT_FOUND" in msg or "INVALID_PASSWORD" in msg:
            _LOGGER.error("Invalid email and password combination")
        else:
            _LOGGER.error(msg)


class ThermoworksSmokeSensor(SensorEntity):
    """Implementation of a thermoworks smoke sensor."""

    def __init__(self, sensor_type, serial, mgr):
        """Initialize the sensor."""
        self.type = sensor_type
        self.serial = serial
        self.mgr = mgr
        self._attr_name = "{name} {sensor}".format(
            name=mgr.name(serial), sensor=SENSOR_TYPES[sensor_type]
        )
        self._attr_native_unit_of_measurement = TEMP_FAHRENHEIT
        self._attr_unique_id = f"{serial}-{sensor_type}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self.update_unit()

    def update_unit(self):
        """Set the units from the data."""
        if PROBE_2 in self.type:
            self._attr_native_unit_of_measurement = self.mgr.units(self.serial, PROBE_2)
        else:
            self._attr_native_unit_of_measurement = self.mgr.units(self.serial, PROBE_1)

    def update(self):
        """Get the monitored data from firebase."""

        try:
            values = self.mgr.data(self.serial)

            # set state from data based on type of sensor
            self._attr_native_value = values.get(camelcase(self.type))

            # set units
            self.update_unit()

            # set basic attributes for all sensors
            self._attr_extra_state_attributes = {
                "time": values["time"],
                "localtime": values["localtime"],
            }

            # set extended attributes for main probe sensors
            if self.type in (PROBE_1, PROBE_2):
                for key, val in values.items():
                    # add all attributes that don't contain any probe name
                    # or contain a matching probe name
                    if (self.type == PROBE_1 and key.find(PROBE_2) == -1) or (
                        self.type == PROBE_2 and key.find(PROBE_1) == -1
                    ):
                        if key == BATTERY_LEVEL:
                            key = ATTR_BATTERY_LEVEL
                        else:
                            # strip probe label and convert to snake_case
                            key = snakecase(key.replace(self.type, ""))
                        # add to attrs
                        if key and key not in EXCLUDE_KEYS:
                            self._attr_extra_state_attributes[key] = val
                # store actual unit because attributes are not converted
                self._attr_extra_state_attributes[
                    "unit_of_min_max"
                ] = self._attr_native_unit_of_measurement

        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
