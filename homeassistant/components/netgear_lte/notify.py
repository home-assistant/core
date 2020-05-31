"""Support for Netgear LTE notifications."""
import logging

import attr
import eternalegypt

from homeassistant.components.notify import ATTR_TARGET, DOMAIN, BaseNotificationService

from . import CONF_RECIPIENT, DATA_KEY

_LOGGER = logging.getLogger(__name__)


async def async_get_service(hass, config, discovery_info=None):
    """Get the notification service."""
    if discovery_info is None:
        return

    return NetgearNotifyService(hass, discovery_info)


@attr.s
class NetgearNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    hass = attr.ib()
    config = attr.ib()

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""

        modem_data = self.hass.data[DATA_KEY].get_modem_data(self.config)
        if not modem_data:
            _LOGGER.error("Modem not ready")
            return

        targets = kwargs.get(ATTR_TARGET, self.config[DOMAIN][CONF_RECIPIENT])
        if not targets:
            _LOGGER.warning("No recipients")
            return

        if not message:
            return

        for target in targets:
            try:
                await modem_data.modem.sms(target, message)
            except eternalegypt.Error:
                _LOGGER.error("Unable to send to %s", target)
