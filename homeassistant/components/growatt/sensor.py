"""Support for Growatt Plant energy production sensors."""
import logging

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

POWER_KILO_WATT = "kW"
ENERGY_MEGA_WATT_HOUR = "MWh"
ENERGY_GIGA_WATT_HOUR = "GWh"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Growatt Plant sensor."""
    import growatt

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    growatt_client = growatt.GrowattApi()

    if login(growatt_client, username, password):
        sensor_today = GrowattPlantTotals(
            growatt_client,
            username,
            password,
            "Growatt plant today",
            "todayEnergySum",
        )
        sensor_total = GrowattPlantTotals(
            growatt_client,
            username,
            password,
            "Growatt plant total",
            "totalEnergySum",
        )
        sensor_current = GrowattPlantCurrent(
            growatt_client, username, password
        )
        add_entities([sensor_today, sensor_total, sensor_current])


def login(client, username, password):
    """Login to the growatt server."""
    import growatt

    try:
        client.login(username, password)
        return True
    except growatt.LoginError as error:
        _LOGGER.error(error)
        return False


class GrowattPlant(Entity):
    """Base Growatt sensor class."""

    def __init__(self, client, username, password):
        """Initialize the sensor."""
        self._client = client
        self._username = username
        self._password = password
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @staticmethod
    def convert_multiplier(metric_name, multiplier_lookup):
        """Convert a value to a given multiplier."""
        if metric_name not in multiplier_lookup:
            message = (
                "Found an unsupported metric name {}"
                "cannot convert safely to kWh."
            ).format(metric_name)
            _LOGGER.error(message)
            raise HomeAssistantError(message)
        return multiplier_lookup[metric_name]


class GrowattPlantTotals(GrowattPlant):
    """Representation of a Growatt plant sensor."""

    def __init__(self, client, username, password, name, metric_name):
        """Initialize the sensor."""
        super().__init__(client, username, password)
        self._name = name
        self._metric_name = metric_name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return ENERGY_KILO_WATT_HOUR

    def _convert_to_kwh(self, value: str, metric_name: str):
        """Convert a value to a kWh value."""
        watts = float(value)
        multiplier_lookup = {
            ENERGY_KILO_WATT_HOUR: 1,
            ENERGY_MEGA_WATT_HOUR: 1000,
            ENERGY_GIGA_WATT_HOUR: 1000 * 1000,
        }
        return watts * self.convert_multiplier(metric_name, multiplier_lookup)

    def _get_total_energy(self, key: str):
        """Get todays energy as float in kWh.

        Refreshes login to update the session.
        """
        if not login(self._client, self._username, self._password):
            raise HomeAssistantError("Not able to login to growatt server.")
        plant_info = self._client.plant_list()
        return self._convert_to_kwh(*plant_info["totalData"][key].split(" "))

    def update(self):
        """Get the latest data from Growatt server."""
        try:
            self._state = self._get_total_energy(self._metric_name)
        except HomeAssistantError as error:
            _LOGGER.error(error)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.name


class GrowattPlantCurrent(GrowattPlant):
    """Representation of a Growatt plant current sensor."""

    def _convert_to_w(self, value: str, metric_name: str):
        """Convert a value to a kWh value."""
        watts = float(value)
        multiplier_lookup = {POWER_WATT: 1, POWER_KILO_WATT: 1000}
        return watts * self.convert_multiplier(metric_name, multiplier_lookup)

    def update(self):
        """Get total current energy as float in W.

        Refreshes login to update the session.
        """
        if not login(self._client, self._username, self._password):
            _LOGGER.error("Not able to login to growatt server.")
            return

        plant_info = self._client.plant_list()
        new_state = float(
            self._convert_to_w(
                *plant_info["totalData"]["currentPowerSum"].split(" ")
            )
        )
        self._state = new_state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return POWER_WATT

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Growatt plant current"
