"""Support for Enphase Envoy solar energy monitor."""
import logging

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MONITORED_CONDITIONS,
    POWER_WATT,
    ENERGY_WATT_HOUR,
)


_LOGGER = logging.getLogger(__name__)

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
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)): vol.All(
            cv.ensure_list, [vol.In(list(SENSORS))]
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Enphase Envoy sensor."""
    from envoy_reader.envoy_reader import EnvoyReader

    ip_address = config[CONF_IP_ADDRESS]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    entities = []
    # Iterate through the list of sensors
    for condition in monitored_conditions:
        if condition == "inverters":
            inverters = await EnvoyReader(ip_address).inverters_production()
            if isinstance(inverters, dict):
                for inverter in inverters:
                    entities.append(
                        Envoy(
                            ip_address,
                            condition,
                            "{} {}".format(SENSORS[condition][0], inverter),
                            SENSORS[condition][1],
                        )
                    )
        else:
            entities.append(
                Envoy(
                    ip_address, condition, SENSORS[condition][0], SENSORS[condition][1]
                )
            )
    async_add_entities(entities)


class Envoy(Entity):
    """Implementation of the Enphase Envoy sensors."""

    def __init__(self, ip_address, sensor_type, name, unit):
        """Initialize the sensor."""
        self._ip_address = ip_address
        self._name = name
        self._unit_of_measurement = unit
        self._type = sensor_type
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    async def async_update(self):
        """Get the energy production data from the Enphase Envoy."""
        from envoy_reader.envoy_reader import EnvoyReader

        if self._type != "inverters":
            _state = await getattr(EnvoyReader(self._ip_address), self._type)()
            if isinstance(_state, int):
                self._state = _state
            else:
                _LOGGER.error(_state)
                self._state = None

        elif self._type == "inverters":
            inverters = await (EnvoyReader(self._ip_address).inverters_production())
            if isinstance(inverters, dict):
                serial_number = self._name.split(" ")[2]
                self._state = inverters[serial_number]
            else:
                self._state = None
