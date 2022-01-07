"""Signal Messenger for notify component."""
from __future__ import annotations

import logging
from typing import Any

from pysignalclirestapi import SignalCliRestApi, SignalCliRestApiError
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_NR = "number"
CONF_RECP_NR = "recipients"
CONF_SIGNAL_CLI_REST_API = "url"
CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 52428800
ATTR_FILENAMES = "attachments"
ATTR_URLS = "urls"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENDER_NR): cv.string,
        vol.Required(CONF_SIGNAL_CLI_REST_API): cv.string,
        vol.Required(CONF_RECP_NR): vol.All(cv.ensure_list, [cv.string]),
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SignalNotificationService:
    """Get the SignalMessenger notification service."""

    sender_nr = config[CONF_SENDER_NR]
    recp_nrs = config[CONF_RECP_NR]
    signal_cli_rest_api_url = config[CONF_SIGNAL_CLI_REST_API]

    signal_cli_rest_api = SignalCliRestApi(signal_cli_rest_api_url, sender_nr)

    return SignalNotificationService(recp_nrs, signal_cli_rest_api)


class SignalNotificationService(BaseNotificationService):
    """Implement the notification service for SignalMessenger."""

    def __init__(
        self,
        recp_nrs: list[str],
        signal_cli_rest_api: SignalCliRestApi,
    ) -> None:
        """Initialize the service."""

        self._recp_nrs = recp_nrs
        self._signal_cli_rest_api = signal_cli_rest_api

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a one or more recipients. Additionally a file can be attached."""

        _LOGGER.debug("Sending signal message")

        data = kwargs.get(ATTR_DATA)

        filenames = self.get_filenames(data)
        attachments_as_bytes = self.get_attachments_as_bytes(
            data, CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES
        )

        try:
            self._signal_cli_rest_api.send_message(
                message, self._recp_nrs, filenames, attachments_as_bytes
            )
        except SignalCliRestApiError as ex:
            _LOGGER.error("%s", ex)
            raise ex

    @staticmethod
    def get_filenames(data: Any) -> list[str] | None:
        """Extract attachment filenames from data."""
        if data is None:
            return None

        if ATTR_FILENAMES in data:
            if isinstance(data[ATTR_FILENAMES], list):
                return data[ATTR_FILENAMES]
            else:
                raise ValueError(
                    "'{property}' property must be a list".format(
                        property=ATTR_FILENAMES
                    )
                )

        return None

    @staticmethod
    def get_attachments_as_bytes(
        data: Any, attachment_size_limit: int
    ) -> list[bytearray] | None:
        """Retrieve attachments from URLs defined in data."""
        if data is None or ATTR_URLS not in data:
            return None

        if not isinstance(data[ATTR_URLS], list):
            raise ValueError(f"'{ATTR_URLS}' property must be a list")

        attachments_as_bytes: list[bytearray] = []

        urls = data[ATTR_URLS]
        for url in urls:
            try:
                resp = requests.get(url, verify=False, timeout=10, stream=True)
                resp.raise_for_status()

                if (
                    resp.headers.get("Content-Length") is not None
                    and int(str(resp.headers.get("Content-Length")))
                    > attachment_size_limit
                ):
                    raise ValueError("Attachment too large (Content-Length)")

                size = 0
                chunks = bytearray()
                for chunk in resp.iter_content(1024):
                    size += len(chunk)
                    if size > attachment_size_limit:
                        raise ValueError("Attachment too large (Stream)")

                    chunks.extend(chunk)

                attachments_as_bytes.append(chunks)
            except Exception as ex:
                _LOGGER.error("%s", ex)
                raise ex

        return attachments_as_bytes
