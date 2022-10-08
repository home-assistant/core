"""Support for SMS notification services."""
import logging

import gammu  # pylint: disable=import-error

from homeassistant.components.notify import ATTR_DATA, BaseNotificationService
from homeassistant.const import CONF_TARGET

from .const import CONF_UNICODE, DOMAIN, GATEWAY, SMS_GATEWAY

_LOGGER = logging.getLogger(__name__)


async def async_get_service(hass, config, discovery_info=None):
    """Get the SMS notification service."""

    if discovery_info is None:
        return None

    return SMSNotificationService(hass)


class SMSNotificationService(BaseNotificationService):
    """Implement the notification service for SMS."""

    def __init__(self, hass):
        """Initialize the service."""

        self.hass = hass

    async def async_send_message(self, message="", **kwargs):
        """Send SMS message."""

        if SMS_GATEWAY not in self.hass.data[DOMAIN]:
            _LOGGER.error("SMS gateway not found, cannot send message")
            return

        gateway = self.hass.data[DOMAIN][SMS_GATEWAY][GATEWAY]

        targets = kwargs.get(CONF_TARGET)
        if targets is None:
            _LOGGER.error("No target number specified, cannot send message")
            return

        extended_data = kwargs.get(ATTR_DATA)
        _LOGGER.debug("Extended data:%s", extended_data)

        if extended_data is None:
            is_unicode = True
        else:
            is_unicode = extended_data.get(CONF_UNICODE, True)

        smsinfo = {
            "Class": -1,
            "Unicode": is_unicode,
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
                    await gateway.send_sms_async(encoded_message)
                except gammu.GSMError as exc:
                    _LOGGER.error("Sending to %s failed: %s", target, exc)
