"""
Doorbird Doorbell Binary Sensor.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/doorbird/
"""

import asyncio
import datetime
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.doorbird import (DOMAIN as DOORBIRD_DOMAIN,
                                               API_URL)
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, STATE_OFF, STATE_ON)
from homeassistant.util import slugify

DEPENDENCIES = ['doorbird']

_LOGGER = logging.getLogger(__name__)

DOORBELL_EVENT = 'doorbell'
MOTION_EVENT = 'motionsensor'

# Sensor types: Name, device_class, event
SENSOR_TYPES = {
    'doorbell': ['Button', 'occupancy', DOORBELL_EVENT],
    'motion': ['Motion', 'motion', MOTION_EVENT],
}

SENSOR_TIMEOUT = datetime.timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Doorbird doorbell sensor platform."""
    sensors = []
    for doorstation in hass.data.get(DOORBIRD_DOMAIN):

        # This will make HA the only service that gets doorbell events.
        doorstation.device.reset_notifications()

        for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
            sensors.append(DoorbirdBinarySensor(hass, doorstation,
                                                sensor_type))

    add_devices(sensors)


class DoorbirdBinarySensor(BinarySensorDevice):
    """representation of a Doorbird binary sensor."""

    def __init__(self, hass, doorstation, sensor_type):
        """Initialize the sensor."""
        self._name = '{} {}'.format(doorstation.name,
                                    SENSOR_TYPES[sensor_type][0])
        self._state = STATE_OFF
        self._sensor_type = sensor_type
        self._device_class = SENSOR_TYPES[sensor_type][1]
        self._event_type = SENSOR_TYPES[sensor_type][2]
        self._device = doorstation
        self._timeout = SENSOR_TIMEOUT
        self._offtime = datetime.datetime.min

        # Provide an endpoint for the doorstation to call to trigger events
        hass.http.register_view(DoorbirdRequestView())

        # Get the URL of this server
        hass_url = hass.config.api.base_url

        # Override url if another is specified in the doorstation configuration
        if doorstation.custom_url is not None:
            hass_url = doorstation.custom_url

        url = '{}{}/{}'.format(hass_url, API_URL, slugify(self._name))

        _LOGGER.info("DoorBird will connect to this instance via %s",
                     url)

        doorstation.device.subscribe_notification(self._event_type, url)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            slugify(self._name), self.receive_update)

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state is STATE_ON

    @property
    def state(self):
        """Current state of entity."""
        return self._state

    def update(self):
        """Wait for the correct amount of assumed time to pass."""
        if self._offtime <= datetime.datetime.now():
            self._state = STATE_OFF
            self._offtime = datetime.datetime.min

    def receive_update(self):
        """Update state from view that entity is attached."""
        self._state = STATE_ON

        now = datetime.datetime.now()
        self._offtime = now + self._timeout

        self.async_schedule_update_ha_state()


class DoorbirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    url = API_URL
    name = API_URL[1:].replace('/', ':')
    extra_urls = [API_URL + '/{sensor}']

    # pylint: disable=no-self-use
    @asyncio.coroutine
    def get(self, request, sensor):
        """Respond to requests from the device."""
        hass = request.app['hass']

        hass.helpers.dispatcher.async_dispatcher_send(sensor)

        return 'OK'
