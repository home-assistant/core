"""Support for Asterisk Voicemail interface."""

import logging
from typing import Any, cast

from asterisk_mbox import Client as asteriskClient
from asterisk_mbox.commands import (
    CMD_MESSAGE_CDR,
    CMD_MESSAGE_CDR_AVAILABLE,
    CMD_MESSAGE_LIST,
)
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_connect
from homeassistant.helpers.issue_registry import IssueSeverity, create_issue
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "asterisk_mbox"

SIGNAL_DISCOVER_PLATFORM = "asterisk_mbox.discover_platform"
SIGNAL_MESSAGE_REQUEST = "asterisk_mbox.message_request"
SIGNAL_MESSAGE_UPDATE = "asterisk_mbox.message_updated"
SIGNAL_CDR_UPDATE = "asterisk_mbox.message_updated"
SIGNAL_CDR_REQUEST = "asterisk_mbox.message_request"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_PORT): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up for the Asterisk Voicemail box."""
    conf: dict[str, Any] = config[DOMAIN]

    host: str = conf[CONF_HOST]
    port: int = conf[CONF_PORT]
    password: str = conf[CONF_PASSWORD]

    hass.data[DOMAIN] = AsteriskData(hass, host, port, password, config)
    create_issue(
        hass,
        DOMAIN,
        "deprecated_integration",
        breaks_in_ha_version="2024.9.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_integration",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Asterisk Voicemail",
            "mailbox": "mailbox",
        },
    )

    return True


class AsteriskData:
    """Store Asterisk mailbox data."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        password: str,
        config: dict[str, Any],
    ) -> None:
        """Init the Asterisk data object."""

        self.hass = hass
        self.config = config
        self.messages: list[dict[str, Any]] | None = None
        self.cdr: list[dict[str, Any]] | None = None

        dispatcher_connect(self.hass, SIGNAL_MESSAGE_REQUEST, self._request_messages)
        dispatcher_connect(self.hass, SIGNAL_CDR_REQUEST, self._request_cdr)
        dispatcher_connect(self.hass, SIGNAL_DISCOVER_PLATFORM, self._discover_platform)
        # Only connect after signal connection to ensure we don't miss any
        self.client = asteriskClient(host, port, password, self.handle_data)

    @callback
    def _discover_platform(self, component: str) -> None:
        _LOGGER.debug("Adding mailbox %s", component)
        self.hass.async_create_task(
            discovery.async_load_platform(
                self.hass, "mailbox", component, {}, self.config
            )
        )

    @callback
    def handle_data(
        self, command: int, msg: list[dict[str, Any]] | dict[str, Any]
    ) -> None:
        """Handle changes to the mailbox."""

        if command == CMD_MESSAGE_LIST:
            msg = cast(list[dict[str, Any]], msg)
            _LOGGER.debug("AsteriskVM sent updated message list: Len %d", len(msg))
            old_messages = self.messages
            self.messages = sorted(
                msg, key=lambda item: item["info"]["origtime"], reverse=True
            )
            if not isinstance(old_messages, list):
                async_dispatcher_send(self.hass, SIGNAL_DISCOVER_PLATFORM, DOMAIN)
            async_dispatcher_send(self.hass, SIGNAL_MESSAGE_UPDATE, self.messages)
        elif command == CMD_MESSAGE_CDR:
            msg = cast(dict[str, Any], msg)
            _LOGGER.debug(
                "AsteriskVM sent updated CDR list: Len %d", len(msg.get("entries", []))
            )
            self.cdr = msg["entries"]
            async_dispatcher_send(self.hass, SIGNAL_CDR_UPDATE, self.cdr)
        elif command == CMD_MESSAGE_CDR_AVAILABLE:
            if not isinstance(self.cdr, list):
                _LOGGER.debug("AsteriskVM adding CDR platform")
                self.cdr = []
                async_dispatcher_send(
                    self.hass, SIGNAL_DISCOVER_PLATFORM, "asterisk_cdr"
                )
            async_dispatcher_send(self.hass, SIGNAL_CDR_REQUEST)
        else:
            _LOGGER.debug(
                "AsteriskVM sent unknown message '%d' len: %d", command, len(msg)
            )

    @callback
    def _request_messages(self) -> None:
        """Handle changes to the mailbox."""
        _LOGGER.debug("Requesting message list")
        self.client.messages()

    @callback
    def _request_cdr(self) -> None:
        """Handle changes to the CDR."""
        _LOGGER.debug("Requesting CDR list")
        self.client.get_cdr()
