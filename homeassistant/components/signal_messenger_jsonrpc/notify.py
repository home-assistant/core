"""Signal Messenger (JSONRPC) for notify component."""
from __future__ import annotations

import logging
from typing import Any

from pysignalclijsonrpc.api import SignalCliJSONRPCApi, SignalCliJSONRPCError
from requests import Session
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

CONF_ACCOUNT = "account"
CONF_RECICPIENTS = "recipients"
CONF_SIGNAL_CLI_REST_API_URL = "url"
CONF_SIGNAL_CLI_REST_API_USERNAME = "username"
CONF_SIGNAL_CLI_REST_API_PASSWORD = "password"
CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 52428800
ATTR_FILENAMES = "attachments"
ATTR_URLS = "urls"
ATTR_VERIFY_SSL = "verify_ssl"

DATA_FILENAMES_SCHEMA = vol.Schema({vol.Required(ATTR_FILENAMES): [cv.string]})

DATA_URLS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URLS): [cv.url],
        vol.Optional(ATTR_VERIFY_SSL, default=True): cv.boolean,
    }
)

DATA_SCHEMA = vol.Any(
    None,
    DATA_FILENAMES_SCHEMA,
    DATA_URLS_SCHEMA,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCOUNT): cv.string,
        vol.Required(CONF_SIGNAL_CLI_REST_API_URL): cv.string,
        vol.Optional(CONF_SIGNAL_CLI_REST_API_USERNAME, default=""): cv.string,
        vol.Optional(CONF_SIGNAL_CLI_REST_API_PASSWORD, default=""): cv.string,
        vol.Required(CONF_RECICPIENTS): vol.All(cv.ensure_list, [cv.string]),
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SignalNotificationService:
    """Get the SignalMessenger notification service."""

    account = config[CONF_ACCOUNT]
    recipients = config[CONF_RECICPIENTS]
    signal_cli_rest_api_url = config[CONF_SIGNAL_CLI_REST_API_URL]
    signal_cli_rest_api_username = config[CONF_SIGNAL_CLI_REST_API_USERNAME]
    signal_cli_rest_api_password = config[CONF_SIGNAL_CLI_REST_API_PASSWORD]
    opts = {
        "endpoint": signal_cli_rest_api_url,
        "account": account,
    }
    if signal_cli_rest_api_username and signal_cli_rest_api_password:
        opts.update(
            {"auth": (signal_cli_rest_api_username, signal_cli_rest_api_password)}
        )
    signal_cli_rest_api = SignalCliJSONRPCApi(**opts)
    return SignalNotificationService(hass, recipients, signal_cli_rest_api)


class SignalNotificationService(BaseNotificationService):
    """Implement the notification service for SignalMessenger."""

    _session = Session()

    def __init__(
        self,
        hass: HomeAssistant,
        recipients: list[str],
        signal_cli_rest_api: SignalCliJSONRPCApi,
    ) -> None:
        """Initialize the service."""

        self._hass = hass
        self._recipients = recipients
        self._signal_cli_rest_api = signal_cli_rest_api

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a one or more recipients. Additionally a file can be attached."""

        _LOGGER.debug("Sending signal message")

        data = kwargs.get(ATTR_DATA)

        try:
            data = DATA_SCHEMA(data)
        except vol.Invalid as ex:
            _LOGGER.error("Invalid message data: %s", ex)
            raise ex

        attachments_as_files = self.get_filenames(data)
        attachments_as_bytes = self.get_attachments_as_bytes(
            data, CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES, self._hass
        )

        try:
            self._signal_cli_rest_api.send_message(
                message=message,
                recipients=self._recipients,
                attachments_as_files=attachments_as_files,
                attachments_as_bytes=attachments_as_bytes,
            )
        except SignalCliJSONRPCError as ex:
            _LOGGER.error("%s", ex)
            raise ex

    @staticmethod
    def get_filenames(data: Any) -> list[str] | None:
        """Extract attachment filenames from data."""
        try:
            data = DATA_FILENAMES_SCHEMA(data)
        except vol.Invalid:
            return None

        return data[ATTR_FILENAMES]

    @classmethod
    def get_attachments_as_bytes(
        cls,
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

                resp = cls._session.get(
                    url, verify=data[ATTR_VERIFY_SSL], timeout=10, stream=True
                )
                resp.raise_for_status()

                if (
                    resp.headers.get("Content-Length") is not None
                    and int(str(resp.headers.get("Content-Length")))
                    > attachment_size_limit
                ):
                    raise ValueError(
                        "Attachment too large (Content-Length reports {}). Max size: {} bytes".format(
                            int(str(resp.headers.get("Content-Length"))),
                            CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES,
                        )
                    )

                size = 0
                chunks = bytearray()
                for chunk in resp.iter_content(1024):
                    size += len(chunk)
                    if size > attachment_size_limit:
                        raise ValueError(
                            "Attachment too large (Stream reports {}). Max size: {} bytes".format(
                                size, CONF_MAX_ALLOWED_DOWNLOAD_SIZE_BYTES
                            )
                        )

                    chunks.extend(chunk)

                attachments_as_bytes.append(chunks)
            except Exception as ex:
                _LOGGER.error("%s", ex)
                raise ex

        if not attachments_as_bytes:
            return None

        return attachments_as_bytes
