"""Support for Enphase Envoy solar energy monitor."""
from datetime import timedelta
import json
import logging

from envoy_reader.envoy_reader import EnvoyReader
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_SCAN_INTERVAL = timedelta(seconds=30)

SENSORS = {
    "production": ("Envoy Current Energy Production", POWER_WATT),
    "daily_production": ("Envoy Today's Energy Production", ENERGY_WATT_HOUR),
    "seven_days_production": (
        "Envoy Last Seven Days Energy Production",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_production": ("Envoy Lifetime Energy Production", ENERGY_WATT_HOUR),
    "consumption": ("Envoy Current Energy Consumption", POWER_WATT),
    "daily_consumption": ("Envoy Today's Energy Consumption", ENERGY_WATT_HOUR),
    "seven_days_consumption": (
        "Envoy Last Seven Days Energy Consumption",
        ENERGY_WATT_HOUR,
    ),
    "lifetime_consumption": ("Envoy Lifetime Energy Consumption", ENERGY_WATT_HOUR),
    "inverters": ("Envoy Inverter", POWER_WATT),
}


ICON = "mdi:flash"
CONST_DEFAULT_HOST = "envoy"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_IP_ADDRESS, default=CONST_DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default="envoy"): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(list(SENSORS))]
        ),
        vol.Optional(CONF_NAME, default=""): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Enphase Envoy sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    envoy_reader = EnvoyReader(ip_address, username, password)

    envoy_data = EnvoyData(envoy_reader)
    await envoy_data.update()

    entities = []
    # Iterate through the list of sensors
    for condition in monitored_conditions:
        if condition == "inverters":
            try:
                inverters = await envoy_reader.inverters_production()
            except requests.exceptions.HTTPError:
                _LOGGER.error(
                    "Authentication for Inverter data failed during setup: %s",
                    ip_address,
                )
                continue

            if isinstance(inverters, dict):
                for inverter in inverters:
                    entities.append(
                        EnvoySensor(
                            envoy_data,
                            condition,
                            f"{name}{SENSORS[condition][0]} {inverter}",
                            SENSORS[condition][1],
                        )
                    )

        else:
            entities.append(
                EnvoySensor(
                    envoy_data,
                    condition,
                    f"{name}{SENSORS[condition][0]}",
                    SENSORS[condition][1],
                )
            )
    async_add_entities(entities)


class EnvoySensor(Entity):
    """Implementation of the Enphase Envoy sensors."""

    def __init__(self, envoy_data, sensor_type, name, unit):
        """Initialize the sensor."""
        self.envoy_data = envoy_data
        self.sensor_type = sensor_type
        self.sensor_name = name
        self.sensor_unit_of_measurement = unit
        self.sensor_state = None
        self.last_reported = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.sensor_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.sensor_state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.sensor_unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.sensor_type == "inverters":
            return {"last_reported": self.last_reported}

        return None

    async def async_update(self):
        """Get the latest data from the Enphase Envoy device."""
        await self.envoy_data.update()
        self.envoy_data.set_state(self)
        self.envoy_data.set_entity_attributes(self)


class EnvoyData:
    """Get the latest data from the Enphase Envoy device."""

    def __init__(self, envoy_reader):
        """Initialize the data object."""
        self._envoy_reader = envoy_reader
        self.data = {}

    @Throttle(MIN_SCAN_INTERVAL)
    async def update(self):
        """Get the latest data from the Enphase Envoy device."""
        try:
            self.data = await self._envoy_reader.update()
            _LOGGER.debug("API data: %s", self.data)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.Timeout,
            json.decoder.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            ConnectionError,
            ValueError,
        ) as err:
            _LOGGER.error("Exception: %s", err)
            self.data = {}

    def set_state(self, envoy_data):
        """Set the sensor value from the dictionary."""
        if envoy_data.sensor_type != "inverters":
            if isinstance(self.data.get(envoy_data.sensor_type), int):
                envoy_data.sensor_state = self.data.get(envoy_data.sensor_type)
                _LOGGER.debug(
                    "Updating: %s - %s", envoy_data.sensor_type, envoy_data.sensor_state
                )
            else:
                _LOGGER.debug(
                    "Sensor %s isInstance(int) was %s.  Returning None for state.",
                    envoy_data.type,
                    isinstance(self.data.get(envoy_data.sensor_type), int),
                )
        elif envoy_data.sensor_type == "inverters":
            serial_number = envoy_data.sensor_name.split(" ")[2]
            if isinstance(self.data.get("inverters_production"), dict):
                envoy_data.sensor_state = self.data.get("inverters_production").get(
                    serial_number
                )[0]
                _LOGGER.debug(
                    "Updating: %s (%s) - %s",
                    envoy_data.sensor_type,
                    serial_number,
                    envoy_data.sensor_state,
                )
            else:
                _LOGGER.debug(
                    "Data inverter (%s) isInstance(dict) was %s.  Using previous state: %s",
                    serial_number,
                    isinstance(self.data.get("inverters_production"), dict),
                    envoy_data.sensor_state,
                )
                # Sometimes the HTTP connection for Inverters to the Envoy will fail which will cause a None value
                # to be returned.  When this occurs the HA sensor will just return the previously
                # known state.  Should this be done here or in HA itself through a template?

    def set_entity_attributes(self, envoy_data):
        """Set attribute data for Inverters."""
        if envoy_data.sensor_type == "inverters":
            serial_number = envoy_data.sensor_name.split(" ")[2]
            if isinstance(self.data.get("inverters_production"), dict):
                envoy_data.last_reported = self.data.get("inverters_production").get(
                    serial_number
                )[1]
                _LOGGER.debug(
                    "Updating: %s (%s) - %s",
                    envoy_data.sensor_type,
                    serial_number,
                    envoy_data.last_reported,
                )
            else:
                _LOGGER.debug(
                    "Data inverter (%s) attrib isInstance(dict) was %s. Not updating attrib.",
                    serial_number,
                    isinstance(self.data.get("inverters_production"), dict),
                )
        else:
            _LOGGER.debug("Skipping, no attributes for: %s", envoy_data.sensor_type)
