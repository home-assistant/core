"""
Support for Growatt Plant energy production sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.growatt/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ["growatt==0.0.2"]

_LOGGER = logging.getLogger(__name__)

UNIT = "kWh"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Growatt Plant sensor."""
    import growatt

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    growatt_client = growatt.GrowattApi()

    is_login_success = login(growatt_client, username, password)
    if is_login_success:
        sensor_today = GrowattPlantToday(
            hass, growatt_client, username, password
        )
        sensor_total = GrowattPlantTotal(
            hass, growatt_client, username, password
        )
        add_entities([sensor_today, sensor_total])
        return True

    return False


def login(client, username, password):
    """Login to the growatt server."""
    import growatt

    try:
        client.login(username, password)
        return True
    except growatt.LoginError as error:
        logging.error(error)
        return False


class GrowattPlant(Entity):
    """Representation of a Growatt plant sensor."""

    def __init__(self, hass, client, username, password):
        """Initialize the sensor."""
        self._hass = hass
        self._unit_of_measurement = UNIT
        self._state = None
        self._client = client
        self._username = username
        self._password = password

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @staticmethod
    def _convert_to_kwh(value: str, metric_name: str):
        """Convert a value to a kWh value."""
        watts = float(value)
        multiplier_lookup = {"kWh": 1, "MWh": 1000, "GWh": 1000 * 1000}
        if metric_name not in multiplier_lookup:
            message = (
                "Found an unsupported metric name {}"
                "cannot convert safely to kWh."
            ).format(metric_name)
            logging.error(message)
            raise ValueError(message)

        multiplier = multiplier_lookup[metric_name]
        return watts * multiplier

    @staticmethod
    def _extract_energy(plant_info_data, key):
        """Extract energy as float from a string."""
        watts = [_[key] for _ in plant_info_data]
        energies = [GrowattPlant._convert_to_kwh(*_.split(" ")) for _ in watts]
        return sum(energies)

    def todays_energy_total(self):
        """Get todays energy as float in kWh.

        Refreshes login to update the session.
        """
        login(self._client, self._username, self._password)
        plant_info = self._client.plant_list()
        return self._extract_energy(plant_info["data"], "todayEnergy")

    def global_energy_total(self):
        """Get total historic energy as float in kWh.

        Refreshes login to update the session.
        """
        login(self._client, self._username, self._password)
        plant_info = self._client.plant_list()
        return self._extract_energy(plant_info["data"], "totalEnergy")


class GrowattPlantToday(GrowattPlant):
    """Representation of a Growatt plant daily sensor."""

    def update(self):
        """Get the latest data from Growatt server."""
        self._state = self.todays_energy_total()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Growatt plant today"


class GrowattPlantTotal(GrowattPlant):
    """Representation of a Growatt plant total sensor."""

    def update(self):
        """Get the latest data from Growatt server."""
        self._state = self.global_energy_total()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Growatt plant total"
