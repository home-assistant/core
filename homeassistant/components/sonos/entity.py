"""Entity representing a Sonos player."""
from __future__ import annotations

import logging
from typing import Any

from pysonos.core import SoCo

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import SonosData
from .const import SONOS_ENTITY_UPDATE, SONOS_STATE_UPDATED
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


class SonosEntity(Entity):
    """Representation of a Sonos entity."""

    def __init__(self, speaker: SonosSpeaker, sonos_data: SonosData):
        """Initialize a SonosEntity."""
        self.speaker = speaker
        self.data = sonos_data

    async def async_added_to_hass(self) -> None:
        """Handle common setup when added to hass."""
        await self.speaker.async_seen()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_ENTITY_UPDATE}-{self.soco.uid}",
                self.update,  # pylint: disable=no-member
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_STATE_UPDATED}-{self.soco.uid}",
                self.async_write_state,
            )
        )

    @property
    def soco(self) -> SoCo:
        """Return the speaker SoCo instance."""
        return self.speaker.soco

    @property
    def device_info(self) -> dict[str, Any]:
        """Return information about the device."""
        return self.speaker.device_info

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available

    @property
    def should_poll(self) -> bool:
        """Return that we should not be polled (we handle that internally)."""
        return False

    @callback
    def async_write_state(self) -> None:
        """Flush the current entity state."""
        self.async_write_ha_state()
