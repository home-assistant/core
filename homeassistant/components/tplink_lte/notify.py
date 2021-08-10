"""Support for TP-Link LTE notifications."""
import logging

import attr
import tp_connected

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import CONF_RECIPIENT

from . import DATA_KEY

_LOGGER = logging.getLogger(__name__)


async def async_get_service(hass, config, discovery_info=None):
    """Get the notification service."""
    if discovery_info is None:
        return
    return TplinkNotifyService(hass, discovery_info)


@attr.s
class TplinkNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    hass = attr.ib()
    config = attr.ib()

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""

        modem_data = self.hass.data[DATA_KEY].get_modem_data(self.config)
        if not modem_data:
            _LOGGER.error("No modem available")
            return

        phone = self.config[CONF_RECIPIENT]
        targets = kwargs.get(ATTR_TARGET, phone)
        if targets and message:
            for target in targets:
                try:
                    await modem_data.modem.sms(target, message)
                except tp_connected.Error:
                    _LOGGER.error("Unable to send to %s", target)
