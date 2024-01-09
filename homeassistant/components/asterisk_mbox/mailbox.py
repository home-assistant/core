"""Support for the Asterisk Voicemail interface."""
from __future__ import annotations

from functools import partial
import logging
from typing import Any

from asterisk_mbox import ServerError

from homeassistant.components.mailbox import CONTENT_TYPE_MPEG, Mailbox, StreamError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as ASTERISK_DOMAIN, AsteriskData

_LOGGER = logging.getLogger(__name__)

SIGNAL_MESSAGE_REQUEST = "asterisk_mbox.message_request"
SIGNAL_MESSAGE_UPDATE = "asterisk_mbox.message_updated"


async def async_get_handler(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> Mailbox:
    """Set up the Asterix VM platform."""
    return AsteriskMailbox(hass, ASTERISK_DOMAIN)


class AsteriskMailbox(Mailbox):
    """Asterisk VM Sensor."""

    def __init__(self, hass: HomeAssistant, name: str) -> None:
        """Initialize Asterisk mailbox."""
        super().__init__(hass, name)
        async_dispatcher_connect(
            self.hass, SIGNAL_MESSAGE_UPDATE, self._update_callback
        )

    @callback
    def _update_callback(self, msg: str) -> None:
        """Update the message count in HA, if needed."""
        self.async_update()

    @property
    def media_type(self) -> str:
        """Return the supported media type."""
        return CONTENT_TYPE_MPEG

    @property
    def can_delete(self) -> bool:
        """Return if messages can be deleted."""
        return True

    @property
    def has_media(self) -> bool:
        """Return if messages have attached media files."""
        return True

    async def async_get_media(self, msgid: str) -> bytes:
        """Return the media blob for the msgid."""

        data: AsteriskData = self.hass.data[ASTERISK_DOMAIN]
        client = data.client
        try:
            return await self.hass.async_add_executor_job(
                partial(client.mp3, msgid, sync=True)
            )
        except ServerError as err:
            raise StreamError(err) from err

    async def async_get_messages(self) -> list[dict[str, Any]]:
        """Return a list of the current messages."""
        data: AsteriskData = self.hass.data[ASTERISK_DOMAIN]
        return data.messages or []

    async def async_delete(self, msgid: str) -> bool:
        """Delete the specified messages."""
        data: AsteriskData = self.hass.data[ASTERISK_DOMAIN]
        client = data.client
        _LOGGER.info("Deleting: %s", msgid)
        await self.hass.async_add_executor_job(client.delete, msgid)
        return True
