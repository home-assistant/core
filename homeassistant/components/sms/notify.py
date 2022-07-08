"""Support for SMS notification services."""
import logging

import gammu  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_NAME, CONF_RECIPIENT, CONF_TARGET
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, GATEWAY, SMS_GATEWAY

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_RECIPIENT): cv.string, vol.Optional(CONF_NAME): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the SMS notification service."""

    if SMS_GATEWAY not in hass.data[DOMAIN]:
        _LOGGER.error("SMS gateway not found, cannot initialize service")
        return

    gateway = hass.data[DOMAIN][SMS_GATEWAY][GATEWAY]

    if discovery_info is None:
        number = config[CONF_RECIPIENT]
    else:
        number = discovery_info[CONF_RECIPIENT]

    return SMSNotificationService(gateway, number)


class SMSNotificationService(BaseNotificationService):
    """Implement the notification service for SMS."""

    def __init__(self, gateway, number):
        """Initialize the service."""
        self.gateway = gateway
        self.number = number

    async def async_send_message(self, message="", **kwargs):
        """Send SMS message."""

        targets = kwargs.get(CONF_TARGET, [self.number])
        smsinfo = {
            "Class": -1,
            "Unicode": True,
            "Entries": [{"ID": "ConcatenatedTextLong", "Buffer": message}],
        }
        try:
            # Encode messages
            encoded = gammu.EncodeSMS(smsinfo)
        except gammu.GSMError as exc:
            _LOGGER.error("Encoding message %s failed: %s", message, exc)
            return

        # Send messages
        for encoded_message in encoded:
            # Fill in numbers
            encoded_message["SMSC"] = {"Location": 1}

            for target in targets:
                encoded_message["Number"] = target
                try:
                    # Actually send the message
                    await self.gateway.send_sms_async(encoded_message)
                except gammu.GSMError as exc:
                    _LOGGER.error("Sending to %s failed: %s", target, exc)
