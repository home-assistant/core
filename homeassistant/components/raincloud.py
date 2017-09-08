"""
Support for Melnor RainCloud sprinkler water timer.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/raincloud/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_send

from requests.exceptions import HTTPError, ConnectTimeout

REQUIREMENTS = ['raincloudy==0.0.1']

_LOGGER = logging.getLogger(__name__)

ALLOWED_WATERING_TIME = [5, 10, 15, 30, 45, 60]

CONF_ATTRIBUTION = "Data provided by Melnor Aquatimer.com"
CONF_WATERING_TIME = 'watering_minutes'

NOTIFICATION_ID = 'raincloud_notification'
NOTIFICATION_TITLE = 'Rain Cloud Setup'

DATA_RAINCLOUD = 'raincloud'
DOMAIN = 'raincloud'
DEFAULT_ENTITY_NAMESPACE = 'raincloud'
DEFAULT_WATERING_TIME = 15

SCAN_INTERVAL = timedelta(seconds=20)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
        vol.Optional(CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME):
            vol.All(vol.In(ALLOWED_WATERING_TIME)),
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Melnor RainCloud component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    default_watering_timer = conf.get(CONF_WATERING_TIME)

    try:
        from raincloudy.core import RainCloudy

        raincloud = RainCloudy(username=username, password=password)
        if not raincloud.is_connected:
            return False
        hass.data[DATA_RAINCLOUD] = RainCloudHub(hass,
                                                 raincloud,
                                                 default_watering_timer)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Rain Cloud service: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    return True


class RainCloudHub:
    """Base class for all Raincloud entities."""

    def __init__(self, hass, data, default_watering_timer):
        """Initialize the entity."""
        self.data = data
        self.default_watering_timer = default_watering_timer

        # needs change
        track_time_interval(hass, self._update_hub, SCAN_INTERVAL)
        self._update_hub(SCAN_INTERVAL)

    def _update_hub(self, now):
        """Refresh data from for all child objects."""
        _LOGGER.debug("Updating RainCloud Hub component.")
        self.data.update()
