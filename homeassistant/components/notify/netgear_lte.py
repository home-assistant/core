"""Netgear LTE platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.netgear_lte/
"""

import voluptuous as vol
import attr

from homeassistant.components.notify import (
    BaseNotificationService, ATTR_TARGET, PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

from ..netgear_lte import DATA_KEY


DEPENDENCIES = ['netgear_lte']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
})


async def async_get_service(hass, config, discovery_info=None):
    """Get the notification service."""
    modem_data = hass.data[DATA_KEY].get_modem_data(config)
    phone = config.get(ATTR_TARGET)
    return NetgearNotifyService(modem_data, phone)


@attr.s
class NetgearNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    modem_data = attr.ib()
    phone = attr.ib()

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        targets = kwargs.get(ATTR_TARGET, self.phone)
        if targets and message:
            for target in targets:
                await self.modem_data.modem.sms(target, message)
