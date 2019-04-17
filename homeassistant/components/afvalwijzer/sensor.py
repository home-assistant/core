"""AfvalWijzer component."""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

CONF_ZIPCODE = "zipcode"
CONF_HOUSENUMBER = "housenumber"
CONF_HOUSENUMBERADDITION = "housenumberaddition"
DEFAULT_HOUSENMBERADDITION = ""
REQUIREMENTS = ['afvalwijzerapi==0.0.2']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1440)

MONITORED_CONDITIONS = {
    'restafval': ['Restafval', None, 'mdi:delete'],
    'pmd': ['PMD', None, 'mdi:beer'],
    'gft': ['GFT', None, 'mdi:delete'],
    'papier': ['Papier', None, 'mdi:email-outline'],
    'takken': ['Snoeiafval', None, 'mdi:tree'],
    'kerstboom': ['Kerstbomen', None, 'mdi:pine-tree']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZIPCODE): cv.string,
    vol.Required(CONF_HOUSENUMBER): cv.port,
    vol.Optional(CONF_HOUSENUMBERADDITION,
                 default=DEFAULT_HOUSENMBERADDITION): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the AfvalwijzerSensor sensors."""
    zip = config.get(CONF_ZIPCODE)
    housenumber = config.get(CONF_HOUSENUMBER)
    numberaddition = config.get(CONF_HOUSENUMBERADDITION)

    from afvalwijzer_pkg.afvalwijzerapi import AfvalwijzerAPI
    api = AfvalwijzerAPI(zip, housenumber, numberaddition)
    if not api.available:
        raise PlatformNotReady

    sensors = [AfvalwijzerSensor(api, condition)
               for condition in config[CONF_MONITORED_CONDITIONS]]

    add_devices(sensors, True)


class AfvalwijzerSensor(Entity):
    """Representation of an AfvalwijzerSensor sensor."""

    def __init__(self, api, index):
        """Initialize an AfvalwijzerSensor sensor."""
        self._api = api
        self._garbageType = index
        self._name = MONITORED_CONDITIONS[index][0]
        self._icon = MONITORED_CONDITIONS[index][2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of the value."""
        return ''

    @property
    def state(self):
        """Return the state of the garbagetype."""
        return self._api.getPickupDate(self._garbageType)

    @property
    def available(self):
        """Could the API be accessed during the last update call."""
        return self._api.available

    def update(self):
        """Get the latest data from the Afvalwijzer API."""
        self._api.update()
