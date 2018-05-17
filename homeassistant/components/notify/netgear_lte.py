"""Netgear LTE platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.netgear_lte/
"""

import voluptuous as vol
import attr

from homeassistant.components.notify import (
    BaseNotificationService, ATTR_TARGET, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

from ..netgear_lte import DATA_KEY


DEPENDENCIES = ['netgear_lte']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(ATTR_TARGET): cv.string,
})


async def async_get_service(hass, config, discovery_info=None):
    """Get the notification service."""
    lte_data = hass.data[DATA_KEY].get(config)
    phone = config.get(ATTR_TARGET)
    return NetgearNotifyService(lte_data, phone)


@attr.s
class NetgearNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    lte_data = attr.ib()
    phone = attr.ib()

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        target = kwargs.get(ATTR_TARGET, self.phone)
        if target is not None and message:
            await self.lte_data.eternalegypt.sms(target, message)
