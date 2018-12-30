"""Netgear LTE platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.netgear_lte/
"""

import logging

import voluptuous as vol
import attr

from homeassistant.components.notify import (
    BaseNotificationService, ATTR_TARGET, PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

from ..netgear_lte import DATA_KEY


DEPENDENCIES = ['netgear_lte']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
})


async def async_get_service(hass, config, discovery_info=None):
    """Get the notification service."""
    return NetgearNotifyService(hass, config)


@attr.s
class NetgearNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    hass = attr.ib()
    config = attr.ib()

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        modem_data = self.hass.data[DATA_KEY].get_modem_data(self.config)
        if not modem_data:
            _LOGGER.error("No modem available")
            return

        phone = self.config.get(ATTR_TARGET)
        targets = kwargs.get(ATTR_TARGET, phone)
        if targets and message:
            for target in targets:
                import eternalegypt
                try:
                    await modem_data.modem.sms(target, message)
                except eternalegypt.Error:
                    _LOGGER.error("Unable to send to %s", target)
