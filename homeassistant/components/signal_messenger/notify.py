"""Signal Messenger for notify component."""

from __future__ import annotations

import logging
from typing import Any

from pysignalclirestapi import SignalCliRestApi, SignalCliRestApiError
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_NR = "number"
CONF_RECP_NR = "recipients"
CONF_SIGNAL_CLI_REST_API = "url"
CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 52428800
ATTR_FILENAMES = "attachments"
ATTR_URLS = "urls"
ATTR_VERIFY_SSL = "verify_ssl"
ATTR_TEXTMODE = "text_mode"

TEXTMODE_OPTIONS = ["normal", "styled"]

DATA_FILENAMES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILENAMES): [cv.string],
        vol.Optional(ATTR_TEXTMODE, default="normal"): vol.In(TEXTMODE_OPTIONS),
    }
)

DATA_URLS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URLS): [cv.url],
        vol.Optional(ATTR_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(ATTR_TEXTMODE, default="normal"): vol.In(TEXTMODE_OPTIONS),
    }
)

DATA_SCHEMA = vol.Any(
    None,
    vol.Schema(
        {
            vol.Optional(ATTR_TEXTMODE, default="normal"): vol.In(TEXTMODE_OPTIONS),
        }
    ),
    DATA_FILENAMES_SCHEMA,
    DATA_URLS_SCHEMA,
)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
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

    return SignalNotificationService(hass, recp_nrs, signal_cli_rest_api)


class SignalNotificationService(BaseNotificationService):
    """Implement the notification service for SignalMessenger."""

    def __init__(
        self,
        hass: HomeAssistant,
        recp_nrs: list[str],
        signal_cli_rest_api: SignalCliRestApi,
    ) -> None:
        """Initialize the service."""

        self._hass = hass
        self._recp_nrs = recp_nrs
        self._signal_cli_rest_api = signal_cli_rest_api

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a one or more recipients. Additionally a file can be attached."""

        _LOGGER.debug("Sending signal message")

        data = kwargs.get(ATTR_DATA)

        try:
            data = DATA_SCHEMA(data)
        except vol.Invalid as ex:
            _LOGGER.error("Invalid message data: %s", ex)
            raise

        filenames = self.get_filenames(data)
        attachments_as_bytes = self.get_attachments_as_bytes(
            data, CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES, self._hass
        )
        try:
            self._signal_cli_rest_api.send_message(
                message,
                self._recp_nrs,
                filenames,
                attachments_as_bytes,
                text_mode="normal" if data is None else data.get(ATTR_TEXTMODE),
            )
        except SignalCliRestApiError as ex:
            _LOGGER.error("%s", ex)
            raise

    @staticmethod
    def get_filenames(data: Any) -> list[str] | None:
        """Extract attachment filenames from data."""
        try:
            data = DATA_FILENAMES_SCHEMA(data)
        except vol.Invalid:
            return None
        return data[ATTR_FILENAMES]

    @staticmethod
    def get_attachments_as_bytes(
        data: Any,
        attachment_size_limit: int,
        hass: HomeAssistant,
    ) -> list[bytearray] | None:
        """Retrieve attachments from URLs defined in data."""
        try:
            data = DATA_URLS_SCHEMA(data)
        except vol.Invalid:
            return None
        urls = data[ATTR_URLS]

        attachments_as_bytes: list[bytearray] = []

        for url in urls:
            try:
                if not hass.config.is_allowed_external_url(url):
                    _LOGGER.error("URL '%s' not in allow list", url)
                    continue

                resp = requests.get(
                    url, verify=data[ATTR_VERIFY_SSL], timeout=10, stream=True
                )
                resp.raise_for_status()

                if (
                    resp.headers.get("Content-Length") is not None
                    and int(str(resp.headers.get("Content-Length")))
                    > attachment_size_limit
                ):
                    content_length = int(str(resp.headers.get("Content-Length")))
                    raise ValueError(  # noqa: TRY301
                        "Attachment too large (Content-Length reports "
                        f"{content_length}). Max size: "
                        f"{CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES} bytes"
                    )

                size = 0
                chunks = bytearray()
                for chunk in resp.iter_content(1024):
                    size += len(chunk)
                    if size > attachment_size_limit:
                        raise ValueError(  # noqa: TRY301
                            f"Attachment too large (Stream reports {size}). "
                            f"Max size: {CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES} bytes"
                        )

                    chunks.extend(chunk)

                attachments_as_bytes.append(chunks)
            except Exception as ex:
                _LOGGER.error("%s", ex)
                raise

        if not attachments_as_bytes:
            return None

        return attachments_as_bytes
