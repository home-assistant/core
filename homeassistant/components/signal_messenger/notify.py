"""Signal Messenger for notify component."""
from contextlib import suppress
import logging
import mimetypes
import re
import shutil
import tempfile

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

    @staticmethod
    def _infer_extension(url: str, resp: requests.Response):
        """Infer the extension from the content type header."""
        content_type = resp.headers["content-type"]
        extension = None
        if content_type:
            extension = mimetypes.guess_extension(content_type)
            if extension is None:
                with suppress(IndexError):
                    extension = content_type.split("/")[1]
        if extension is None:
            try:
                extension = url.split(".")[-1]
            except IndexError:
                _LOGGER.warning(
                    "Unable to infer extension from url. Using .jpg as the default extension"
                )
                extension = "jpg"
        return extension

    def send_message(self, message="", **kwargs):
        """Send a message to a one or more recipients.

        Additionally a file can be attached.
        """

        _LOGGER.debug("Sending signal message")

        data = kwargs.get(ATTR_DATA)

        filenames = None
        tmp_dir = None
        if data is not None:
            if ATTR_URLS in data:
                # download urls to temp file
                filenames = []
                tmp_dir = tempfile.mkdtemp()
                if isinstance(ATTR_URLS, list):
                    urls = data[ATTR_URLS]
                else:
                    urls = [data[ATTR_URLS]]
                for i, url in enumerate(urls):
                    resp = requests.get(url)
                    if resp.status_code != 200:
                        raise ValueError(
                            f"Could not download attachment from url {url}"
                        )
                    extension = self._infer_extension(url, resp)
                    with open(f"{tmp_dir}/{i}.{extension}", "wb") as fd:
                        fd.write(resp.content)
                    filenames.append(f"{tmp_dir}/{i}.{extension}")
            elif ATTR_FILENAMES in data:
                if isinstance(ATTR_FILENAMES, list):
                    filenames = data[ATTR_FILENAMES]
                else:
                    filenames = [data[ATTR_FILENAMES]]

        try:
            self._signal_cli_rest_api.send_message(
                message,
                self._recp_nrs,
                filenames=filenames,
            )
        except SignalCliRestApiError as ex:
            _LOGGER.error("%s", ex)
            raise ex
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir)
