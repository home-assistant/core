"""Signal Messenger for notify component."""
import logging
import voluptuous as vol
from pysignalclirestapi import SignalCliRestApi

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_NR = "number"
CONF_RECP_NR = "recipients"
CONF_SIGNAL_CLI_REST_API = "url"
ATTR_FILENAME = "attachment"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SENDER_NR): cv.string,
        vol.Optional(CONF_SIGNAL_CLI_REST_API): cv.string,
        vol.Optional(CONF_RECP_NR): vol.All(cv.ensure_list, [cv.string]),
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the SignalMessenger notification service."""

    sender_nr = config.get(CONF_SENDER_NR)
    recp_nrs = config.get(CONF_RECP_NR)
    signal_cli_rest_api_url = config.get(CONF_SIGNAL_CLI_REST_API)

    if signal_cli_rest_api_url is None:
        _LOGGER.error("Please specify the URL to the signal-cli REST API")
        return None

    if recp_nrs is None:
        _LOGGER.error("Please specify at least one recipient number")
        return None

    if sender_nr is None:
        _LOGGER.error("Please provide a sender number")
        return None

    return SignalNotificationService(sender_nr, recp_nrs, signal_cli_rest_api_url)


class SignalNotificationService(BaseNotificationService):
    """Implement the notification service for SignalMessenger."""

    def __init__(self, sender_nr, recp_nrs, signal_cli_rest_api_url):
        """Initialize the service."""

        self._recp_nrs = recp_nrs
        self._signal_cli_rest_api = SignalCliRestApi(
            signal_cli_rest_api_url, sender_nr, api_version=1
        )

    def send_message(self, message="", **kwargs):
        """Send a message to a one or more recipients.

        Additionally a file can be attached.
        """

        _LOGGER.info("Sending signal message")

        data = kwargs.get(ATTR_DATA, None)

        filename = None
        if data is not None and ATTR_FILENAME in data:
            filename = data[ATTR_FILENAME]

        try:
            self._signal_cli_rest_api.send_message(message, self._recp_nrs, filename)
        except Exception as ex:
            _LOGGER.error("%s", ex)
            raise ex
