"""Signal Messenger for notify component."""
import logging

from pysignalclirestapi import SignalCliRestApi, SignalCliRestApiError
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_NR = "number"
CONF_RECP_NR = "recipients"
CONF_SIGNAL_CLI_REST_API = "url"
CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 52428800
ATTR_FILENAME = "attachment"
ATTR_FILENAMES = "attachments"
ATTR_URLS = "urls"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENDER_NR): cv.string,
        vol.Required(CONF_SIGNAL_CLI_REST_API): cv.string,
        vol.Required(CONF_RECP_NR): vol.All(cv.ensure_list, [cv.string]),
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the SignalMessenger notification service."""

    sender_nr = config[CONF_SENDER_NR]
    recp_nrs = config[CONF_RECP_NR]
    signal_cli_rest_api_url = config[CONF_SIGNAL_CLI_REST_API]

    signal_cli_rest_api = SignalCliRestApi(signal_cli_rest_api_url, sender_nr)

    return SignalNotificationService(recp_nrs, signal_cli_rest_api)


class SignalNotificationService(BaseNotificationService):
    """Implement the notification service for SignalMessenger."""

    def __init__(self, recp_nrs, signal_cli_rest_api):
        """Initialize the service."""

        self._recp_nrs = recp_nrs
        self._signal_cli_rest_api = signal_cli_rest_api

    def send_message(self, message="", **kwargs):
        """Send a message to a one or more recipients. Additionally a file can be attached."""

        _LOGGER.debug("Sending signal message")

        data = kwargs.get(ATTR_DATA)

        filenames = self._get_filenames(data)
        attachments_as_bytes = self._get_attachments_as_bytes(data)

        try:
            self._signal_cli_rest_api.send_message(
                message, self._recp_nrs, filenames, attachments_as_bytes
            )
        except SignalCliRestApiError as ex:
            _LOGGER.error("%s", ex)
            raise ex

    @staticmethod
    def _get_filenames(data):
        filenames = None

        if data is None:
            return None
        if ATTR_FILENAMES in data:
            filenames = data[ATTR_FILENAMES]
        if ATTR_FILENAME in data:
            _LOGGER.warning(
                "The 'attachment' option is deprecated, please replace it with 'attachments'. "
                "This option will become invalid in version 0.108"
            )
            if filenames is None:
                filenames = [data[ATTR_FILENAME]]
            else:
                filenames.append(data[ATTR_FILENAME])

        return filenames

    @staticmethod
    def _get_attachments_as_bytes(data):
        attachments_as_bytes = []

        if data is None or ATTR_URLS not in data:
            return attachments_as_bytes

        urls = data[ATTR_URLS]
        for url in urls:
            try:
                resp = requests.get(url, verify=False, timeout=10, stream=True)
                resp.raise_for_status()

                if (
                    resp.headers.get("Content-Length") is not None
                    and int(resp.headers.get("Content-Length"))
                    > CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES
                ):
                    raise ValueError("Attachment too large")

                size = 0
                chunks = bytearray()
                for chunk in resp.iter_content(1024):
                    size += len(chunk)
                    if size > CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES:
                        raise ValueError("Attachment too large")

                    chunks.extend(chunk)

                attachments_as_bytes.append(chunks)
            except Exception as ex:
                _LOGGER.error("%s", ex)
                raise ex

        return attachments_as_bytes
