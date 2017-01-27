"""
Twilio Call platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.twilio_call/
"""
import logging
import urllib


import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ["twilio==5.4.0"]


CONF_ACCOUNT_SID = "account_sid"
CONF_AUTH_TOKEN = "auth_token"
CONF_FROM_NUMBER = "from_number"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCOUNT_SID): cv.string,
    vol.Required(CONF_AUTH_TOKEN): cv.string,
    vol.Required(CONF_FROM_NUMBER):
        vol.All(cv.string, vol.Match(r"^\+?[1-9]\d{1,14}$")),
})


def get_service(hass, config, discovery_info=None):
    """Get the Twilio Call notification service."""
    # pylint: disable=import-error
    from twilio.rest import TwilioRestClient

    twilio_client = TwilioRestClient(config[CONF_ACCOUNT_SID],
                                     config[CONF_AUTH_TOKEN])

    return TwilioCallNotificationService(twilio_client,
                                         config[CONF_FROM_NUMBER])


def is_validurl(url):
    """Check if the passed url is valid using dperini regex."""
    import re

    ip_middle_oct = u"(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5]))"
    ip_last_oct = u"(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))"

    regex = re.compile(
        u"^"
        # protocol identifier
        u"(?:(?:https?|ftp)://)"
        # user:pass authentication
        u"(?:\S+(?::\S*)?@)?"
        u"(?:"
        u"(?P<private_ip>"
        # IP address exclusion
        # private & local networks
        u"(?:(?:10|127)" + ip_middle_oct + u"{2}" + ip_last_oct + u")|"
        u"(?:(?:169\.254|192\.168)" + ip_middle_oct + ip_last_oct + u")|"
        u"(?:172\.(?:1[6-9]|2\d|3[0-1])" + ip_middle_oct + ip_last_oct + u"))"
        u"|"
        # IP address dotted notation octets
        # excludes loopback network 0.0.0.0
        # excludes reserved space >= 224.0.0.0
        # excludes network & broadcast addresses
        # (first & last IP address of each class)
        u"(?P<public_ip>"
        u"(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])"
        u"" + ip_middle_oct + u"{2}"
        u"" + ip_last_oct + u")"
        u"|"
        # host name
        u"(?:(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+)"
        # domain name
        u"(?:\.(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+)*"
        # TLD identifier
        u"(?:\.(?:[a-z\u00a1-\uffff]{2,}))"
        u")"
        # port number
        u"(?::\d{2,5})?"
        # resource path
        u"(?:/\S*)?"
        # query string
        u"(?:\?\S*)?"
        u"$",
        re.UNICODE | re.IGNORECASE
    )

    return regex.match(url)


class TwilioCallNotificationService(BaseNotificationService):
    """Implement the notification service for the Twilio Call service."""

    def __init__(self, twilio_client, from_number):
        """Initialize the service."""
        self.client = twilio_client
        self.from_number = from_number

    def send_message(self, message="", **kwargs):
        """Call to specified target users."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            _LOGGER.info("At least 1 target is required")
            return

        if is_validurl(message):
            twimlet_url = message
        else:
            twimlet_url = 'http://twimlets.com/message?Message='
            twimlet_url += urllib.parse.quote(message, safe='')

        for target in targets:
            self.client.calls.create(to=target,
                                     url=twimlet_url,
                                     from_=self.from_number)
