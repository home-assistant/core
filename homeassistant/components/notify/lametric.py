"""
Notifier for LaMetric time.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.lametric/
"""
import logging

from requests.exceptions import ConnectionError as RequestsConnectionError
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ICON
import homeassistant.helpers.config_validation as cv

from homeassistant.components.lametric import DOMAIN as LAMETRIC_DOMAIN

REQUIREMENTS = ['lmnotify==0.0.4']
DEPENDENCIES = ['lametric']

_LOGGER = logging.getLogger(__name__)

CONF_LIFETIME = "lifetime"
CONF_CYCLES = "cycles"
CONF_PRIORITY = "priority"

AVAILABLE_PRIORITIES = ["info", "warning", "critical"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ICON, default="i555"): cv.string,
    vol.Optional(CONF_LIFETIME, default=10): cv.positive_int,
    vol.Optional(CONF_CYCLES, default=1): cv.positive_int,
    vol.Optional(CONF_PRIORITY, default="warning"):
        vol.In(AVAILABLE_PRIORITIES)
})


def get_service(hass, config, discovery_info=None):
    """Get the LaMetric notification service."""
    hlmn = hass.data.get(LAMETRIC_DOMAIN)
    return LaMetricNotificationService(hlmn,
                                       config[CONF_ICON],
                                       config[CONF_LIFETIME] * 1000,
                                       config[CONF_CYCLES],
                                       config[CONF_PRIORITY])


class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(self, hasslametricmanager, icon, lifetime, cycles, priority):
        """Initialize the service."""
        self.hasslametricmanager = hasslametricmanager
        self._icon = icon
        self._lifetime = lifetime
        self._cycles = cycles
        self._priority = priority
        self._devices = []

    def send_message(self, message="", **kwargs):
        """Send a message to some LaMetric device."""
        from lmnotify import SimpleFrame, Sound, Model
        from oauthlib.oauth2 import TokenExpiredError

        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)
        _LOGGER.debug("Targets/Data: %s/%s", targets, data)
        icon = self._icon
        cycles = self._cycles
        sound = None
        priority = self._priority

        # Additional data?
        if data is not None:
            if "icon" in data:
                icon = data["icon"]
            if "sound" in data:
                try:
                    sound = Sound(category="notifications",
                                  sound_id=data["sound"])
                    _LOGGER.debug("Adding notification sound %s",
                                  data["sound"])
                except AssertionError:
                    _LOGGER.error("Sound ID %s unknown, ignoring",
                                  data["sound"])
            if "cycles" in data:
                cycles = int(data['cycles'])
            if "priority" in data:
                if data['priority'] in AVAILABLE_PRIORITIES:
                    priority = data['priority']
                else:
                    _LOGGER.warning("Priority %s invalid, using default %s",
                                    data['priority'], priority)

        text_frame = SimpleFrame(icon, message)
        _LOGGER.debug("Icon/Message/Cycles/Lifetime: %s, %s, %d, %d",
                      icon, message, self._cycles, self._lifetime)

        frames = [text_frame]

        model = Model(frames=frames, cycles=cycles, sound=sound)
        lmn = self.hasslametricmanager.manager
        try:
            self._devices = lmn.get_devices()
        except TokenExpiredError:
            _LOGGER.debug("Token expired, fetching new token")
            lmn.get_token()
            self._devices = lmn.get_devices()
        except RequestsConnectionError:
            _LOGGER.warning("Problem connecting to LaMetric, "
                            "using cached devices instead")
        for dev in self._devices:
            if targets is None or dev["name"] in targets:
                try:
                    lmn.set_device(dev)
                    lmn.send_notification(model, lifetime=self._lifetime,
                                          priority=priority)
                    _LOGGER.debug("Sent notification to LaMetric %s",
                                  dev["name"])
                except OSError:
                    _LOGGER.warning("Cannot connect to LaMetric %s",
                                    dev["name"])
