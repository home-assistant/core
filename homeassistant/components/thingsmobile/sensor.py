"""Support for TM sensors."""
from datetime import timedelta
import logging
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required("esim"): cv.string})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """
    Set up the TM sensor - should maybe go async? Fine for now though maybe.

    More information on Docs page
    """
    conf = hass.data["thingsmobile"]
    esim = config.get("esim")
    sensor_list = []
    sensor_list.append(
        ThingsMobileSensor(
            esim,
            conf["url"],
            conf["body"]["username"],
            conf["body"]["token"],
            config.get("name"),
        )
    )
    add_entities(sensor_list, True)


class ThingsMobileSensor(Entity):
    """TM Sensor Class."""

    def __init__(self, esim, api_url, username, token, name=None):
        """Init Function for TM sensor."""
        self._api_url = api_url
        self._username = username
        self._token = token
        self.esim = esim
        self._name = name
        self.units = ""
        self.entity_id = "sensor.tm_{}".format(esim)
        import datetime

        self.last_successful_update = datetime.datetime.now()

        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """TM Sensor update func."""
        import xml.etree.ElementTree as ET

        result = requests.post(
            self._api_url,
            {"username": self._username, "token": self._token, "msisdn": self.esim},
        )
        parsed = ET.fromstring(result.text)
        sims = parsed.findall("./sims/sim")
        for sim in sims:
            self._state = self.get_human_readable(sim.find("./balance").text)
            self._name = sim.find("./name").text

    def get_human_readable(self, size, precision=2):
        """Util function to simplify data."""
        size = int(size)
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        suffix_index = 0
        while size > 1024 and suffix_index < 4:
            suffix_index += 1  # increment the index of the suffix
            size = size / 1024  # apply the division
        self.units = suffixes[suffix_index]
        return size

    def attribute_map(self):
        """Map data to attribs."""
        import datetime

        self.last_successful_update = datetime.datetime.now()

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            "last_successful_update": self.last_successful_update,
            "unit_of_measurement": self.units,
        }
        return state_attr
