"""Support for the Asterisk CDR interface."""
from __future__ import annotations

import datetime
import hashlib
from typing import Any

from homeassistant.components.asterisk_mbox import (
    DOMAIN as ASTERISK_DOMAIN,
    SIGNAL_CDR_UPDATE,
)
from homeassistant.components.mailbox import DOMAIN as MAILBOX_DOMAIN, Mailbox
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

MAILBOX_NAME = "asterisk_cdr"


async def async_get_handler(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> Mailbox:
    """Set up the Asterix CDR platform."""
    async_create_issue(
        hass,
        MAILBOX_DOMAIN,
        f"deprecated_mailbox_integration_{MAILBOX_NAME}",
        breaks_in_ha_version="2024.9.0",
        is_fixable=False,
        issue_domain=MAILBOX_NAME,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_mailbox_integration",
        translation_placeholders={
            "domain": MAILBOX_NAME,
            "integration_title": "Asterisk Call Detail Records",
        },
    )
    return AsteriskCDR(hass, MAILBOX_NAME)


class AsteriskCDR(Mailbox):
    """Asterisk VM Call Data Record mailbox."""

    def __init__(self, hass: HomeAssistant, name: str) -> None:
        """Initialize Asterisk CDR."""
        super().__init__(hass, name)
        self.cdr: list[dict[str, Any]] = []
        async_dispatcher_connect(self.hass, SIGNAL_CDR_UPDATE, self._update_callback)

    @callback
    def _update_callback(self, msg: list[dict[str, Any]]) -> Any:
        """Update the message count in HA, if needed."""
        self._build_message()
        self.async_update()

    def _build_message(self) -> None:
        """Build message structure."""
        cdr: list[dict[str, Any]] = []
        for entry in self.hass.data[ASTERISK_DOMAIN].cdr:
            timestamp = datetime.datetime.strptime(
                entry["time"], "%Y-%m-%d %H:%M:%S"
            ).timestamp()
            info = {
                "origtime": timestamp,
                "callerid": entry["callerid"],
                "duration": entry["duration"],
            }
            sha = hashlib.sha256(str(entry).encode("utf-8")).hexdigest()
            msg = (
                f"Destination: {entry['dest']}\n"
                f"Application: {entry['application']}\n "
                f"Context: {entry['context']}"
            )
            cdr.append({"info": info, "sha": sha, "text": msg})
        self.cdr = cdr

    async def async_get_messages(self) -> list[dict[str, Any]]:
        """Return a list of the current messages."""
        if not self.cdr:
            self._build_message()
        return self.cdr
