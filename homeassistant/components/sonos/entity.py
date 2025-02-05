"""Entity representing a Sonos player."""

from __future__ import annotations

from abc import abstractmethod
import datetime
import logging

from soco.core import SoCo

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DATA_SONOS, DOMAIN, SONOS_FALLBACK_POLL, SONOS_STATE_UPDATED
from .exception import SonosUpdateError
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)


class SonosEntity(Entity):
    """Representation of a Sonos entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, speaker: SonosSpeaker) -> None:
        """Initialize a SonosEntity."""
        self.speaker = speaker

    async def async_added_to_hass(self) -> None:
        """Handle common setup when added to hass."""
        self.hass.data[DATA_SONOS].entity_id_mappings[self.entity_id] = self.speaker
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_FALLBACK_POLL}-{self.soco.uid}",
                self.async_fallback_poll,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_STATE_UPDATED}-{self.soco.uid}",
                self.async_write_ha_state,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        del self.hass.data[DATA_SONOS].entity_id_mappings[self.entity_id]

    async def async_fallback_poll(self, now: datetime.datetime) -> None:
        """Poll the entity if subscriptions fail."""
        if not self.speaker.subscriptions_failed:
            self.speaker.subscriptions_failed = True
            await self.speaker.async_unsubscribe()
        try:
            await self._async_fallback_poll()
        except SonosUpdateError as err:
            _LOGGER.debug("Could not fallback poll: %s", err)

    @abstractmethod
    async def _async_fallback_poll(self) -> None:
        """Poll the specific functionality if subscriptions fail.

        Should be implemented by platforms if needed.
        """

    @property
    def soco(self) -> SoCo:
        """Return the speaker SoCo instance."""
        return self.speaker.soco

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        suggested_area: str | None = None
        if not self.speaker.battery_info:
            # Only set suggested area for non-portable devices
            suggested_area = self.speaker.zone_name
        return DeviceInfo(
            identifiers={(DOMAIN, self.soco.uid)},
            name=self.speaker.zone_name,
            model=self.speaker.model_name.replace("Sonos ", ""),
            model_id=self.speaker.model_number,
            sw_version=self.speaker.version,
            connections={
                (dr.CONNECTION_NETWORK_MAC, self.speaker.mac_address),
                (dr.CONNECTION_UPNP, f"uuid:{self.speaker.uid}"),
            },
            manufacturer="Sonos",
            suggested_area=suggested_area,
            configuration_url=f"http://{self.soco.ip_address}:1400/support/review",
        )

    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self.speaker.available


class SonosPollingEntity(SonosEntity):
    """Representation of a Sonos entity which may not support updating by subscriptions."""

    @abstractmethod
    def poll_state(self) -> None:
        """Poll the device for the current state."""

    def update(self) -> None:
        """Update the state using the built-in entity poller."""
        if not self.available:
            return
        try:
            self.poll_state()
        except SonosUpdateError as err:
            _LOGGER.debug("Could not poll: %s", err)
