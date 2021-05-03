"""Entity representing a Sonos player."""
from __future__ import annotations

import logging

from pysonos.core import SoCo

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DOMAIN,
    SONOS_ENTITY_CREATED,
    SONOS_ENTITY_UPDATE,
    SONOS_STATE_UPDATED,
)
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


class SonosEntity(Entity):
    """Representation of a Sonos entity."""

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize a SonosEntity."""
        self.speaker = speaker

    async def async_added_to_hass(self) -> None:
        """Handle common setup when added to hass."""
        await self.speaker.async_seen()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_ENTITY_UPDATE}-{self.soco.uid}",
                self.async_update,  # pylint: disable=no-member
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_STATE_UPDATED}-{self.soco.uid}",
                self.async_write_ha_state,
            )
        )

    @property
    def soco(self) -> SoCo:
        """Return the speaker SoCo instance."""
        return self.speaker.soco

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, self.soco.uid)},
            "name": self.speaker.zone_name,
            "model": self.speaker.model_name.replace("Sonos ", ""),
            "sw_version": self.speaker.version,
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.speaker.mac_address)},
            "manufacturer": "Sonos",
            "suggested_area": self.speaker.zone_name,
        }

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available

    @property
    def should_poll(self) -> bool:
        """Return that we should not be polled (we handle that internally)."""
        return False


class SonosSensorEntity(SonosEntity):
    """Representation of a Sonos sensor entity."""

    async def async_added_to_hass(self) -> None:
        """Handle common setup when added to hass."""
        await super().async_added_to_hass()
        async_dispatcher_send(
            self.hass, f"{SONOS_ENTITY_CREATED}-{self.soco.uid}", self.platform.domain
        )
