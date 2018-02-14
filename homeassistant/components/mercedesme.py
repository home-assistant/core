"""
Support for MercedesME System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, LENGTH_KILOMETERS)
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['mercedesmejsonpy==0.1.2']

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS = {
    'doorsClosed': ['Doors closed'],
    'windowsClosed': ['Windows closed'],
    'locked': ['Doors locked'],
    'tireWarningLight': ['Tire Warning']
}

SENSORS = {
    'fuelLevelPercent': ['Fuel Level', '%'],
    'fuelRangeKm': ['Fuel Range', LENGTH_KILOMETERS],
    'latestTrip': ['Latest Trip', None],
    'odometerKm': ['Odometer', LENGTH_KILOMETERS],
    'serviceIntervalDays': ['Next Service', 'days']
}

DATA_MME = 'mercedesme'
DOMAIN = 'mercedesme'

FEATURE_NOT_AVAILABLE = "The feature %s is not available for your car %s"

NOTIFICATION_ID = 'mercedesme_integration_notification'
NOTIFICATION_TITLE = 'Mercedes me integration setup'

SIGNAL_UPDATE_MERCEDESME = "mercedesme_update"


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=30):
            vol.All(cv.positive_int, vol.Clamp(min=10))
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up MercedesMe System."""
    from mercedesmejsonpy.controller import Controller
    from mercedesmejsonpy import Exceptions

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        mercedesme_api = Controller(username, password, scan_interval)
        if not mercedesme_api.is_valid_session:
            raise Exceptions.MercedesMeException(500)
        hass.data[DATA_MME] = MercedesMeHub(mercedesme_api)
    except Exceptions.MercedesMeException as ex:
        if ex.code == 401:
            hass.components.persistent_notification.create(
                "Error:<br />Please check username and password."
                "You will need to restart Home Assistant after fixing.",
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
        else:
            hass.components.persistent_notification.create(
                "Error:<br />Can't communicate with Mercedes me API.<br />"
                "Error code: {} Reason: {}"
                "You will need to restart Home Assistant after fixing."
                "".format(ex.code, ex.message),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)

        _LOGGER.error("Unable to communicate with Mercedes me API: %s",
                      ex.message)
        return False

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'device_tracker', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)

    def hub_refresh(event_time):
        """Call Mercedes me API to refresh information."""
        _LOGGER.info("Updating Mercedes me component.")
        hass.data[DATA_MME].data.update()
        dispatcher_send(hass, SIGNAL_UPDATE_MERCEDESME)

    track_time_interval(
        hass,
        hub_refresh,
        timedelta(seconds=scan_interval))

    return True


class MercedesMeHub(object):
    """Representation of a base MercedesMe device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data


class MercedesMeEntity(Entity):
    """Entity class for MercedesMe devices."""

    def __init__(self, data, internal_name, sensor_name, vin, unit):
        """Initialize the MercedesMe entity."""
        self._car = None
        self._data = data
        self._state = False
        self._name = sensor_name
        self._internal_name = internal_name
        self._unit = unit
        self._vin = vin

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_MERCEDESME, self._update_callback)

    def _update_callback(self):
        """Callback update method."""
        # If the method is made a callback this should be changed
        # to the async version. Check core.callback
        self.schedule_update_ha_state(True)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit
