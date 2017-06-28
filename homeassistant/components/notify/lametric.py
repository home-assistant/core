"""
Notify for LaMetric time.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.lametric/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ICON
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from homeassistant.components.lametric import HassLaMetricManager

REQUIREMENTS = ['lmnotify==0.0.4']

_LOGGER = logging.getLogger(__name__)

CONF_DISPLAY_TIME = "display_time"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ICON, default="i555"): cv.string,
    vol.Optional(CONF_DISPLAY_TIME, default=10): cv.positive_int,
})


# pylint: disable=unused-variable
def get_service(hass, config, discovery_info=None):
    """Get the Slack notification service."""

    try:
        return LaMetricNotificationService(config[CONF_ICON],
                                           config[CONF_DISPLAY_TIME] * 1000)
    except HomeAssistantError:
        _LOGGER.exception("Could not configure LaMetric notifier")
        return None


class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(self, icon, display_time):
        """Initialize the service."""
        self._icon = icon
        self._display_time = display_time

    def send_message(self, message="", **kwargs):
        """Send a message to some LaMetric deviced."""
        from lmnotify import SimpleFrame, Sound, Model

        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)
        _LOGGER.debug("Targets/Data: %s/%s", targets, data)
        icon = self._icon
        sound = None

        # User-defined icon?
        if data is not None:
            if "icon" in data:
                icon = data["icon"]
            if "sound" in data:
                try:
                    sound = Sound(category="notifications",
                                  sound_id=data["sound"])
                    _LOGGER.debug("Adding notification sound %s",
                                  data["sound"])
                except Exception:
                    _LOGGER.error("Sound ID %s unknown, ignoring",
                                  data["sound"])

        textFrame = SimpleFrame(icon, message)
        _LOGGER.debug("Icon/Message/Duration: %s, %s, %d",
                      icon, message, self._display_time)

        frames = [textFrame]

        if sound is not None:
            frames.append(sound)

        # Find extra parameters in the data section

        _LOGGER.debug(frames)

        model = Model(frames=frames)

        lmn = HassLaMetricManager.manager()
        devices = lmn.get_devices()
        for d in devices:
            if (targets is None) or (d["name"] in targets):
                lmn.set_device(d)
                lmn.send_notification(model, lifetime=self._display_time)
                _LOGGER.debug("Sent notification to LaMetric %s", d["name"])
