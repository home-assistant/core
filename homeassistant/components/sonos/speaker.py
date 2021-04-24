"""Base class for common speaker tasks."""
from __future__ import annotations

from asyncio import gather
import logging
from typing import Any, Callable

from pysonos.core import SoCo
from pysonos.events_base import Event as SonosEvent, SubscriptionBase
from pysonos.exceptions import SoCoException

from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    dispatcher_connect,
    dispatcher_send,
)

from .const import (
    DOMAIN as SONOS_DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL,
    SEEN_EXPIRE_TIME,
    SONOS_CONTENT_UPDATE,
    SONOS_DISCOVERY_UPDATE,
    SONOS_ENTITY_CREATED,
    SONOS_ENTITY_UPDATE,
    SONOS_GROUP_UPDATE,
    SONOS_MEDIA_UPDATE,
    SONOS_PLAYER_RECONNECTED,
    SONOS_PROPERTIES_UPDATE,
    SONOS_SEEN,
    SONOS_STATE_UPDATED,
    SONOS_VOLUME_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


class SonosSpeaker:
    """Representation of a Sonos speaker."""

    def __init__(self, hass: HomeAssistant, soco: SoCo):
        """Initialize a SonosSpeaker."""
        speaker_info = soco.get_speaker_info(True)

        self._is_ready: bool = False
        self._subscriptions: list[SubscriptionBase] = []
        self._poll_timer: Callable | None = None
        self._seen_timer: Callable | None = None
        self._seen_dispatcher: Callable | None = None
        self._entity_creation_dispatcher: Callable | None = None
        self._platforms_ready: set[str] = set()

        self.hass: HomeAssistant = hass
        self.soco: SoCo = soco

        self.mac_address = speaker_info["mac_address"]
        self.model_name = speaker_info["model_name"]
        self.version = speaker_info["software_version"]
        self.zone_name = speaker_info["zone_name"]

    def setup(self) -> None:
        """Run initial setup of the speaker."""
        self._entity_creation_dispatcher = dispatcher_connect(
            self.hass,
            f"{SONOS_ENTITY_CREATED}-{self.soco.uid}",
            self.async_handle_new_entity,
        )
        self._seen_dispatcher = dispatcher_connect(
            self.hass, f"{SONOS_SEEN}-{self.soco.uid}", self.async_seen
        )
        dispatcher_send(self.hass, SONOS_DISCOVERY_UPDATE, self)

    async def async_handle_new_entity(self, entity_type: str) -> None:
        """Listen to new entities to trigger first subscription."""
        self._platforms_ready.add(entity_type)
        if self._platforms_ready == PLATFORMS:
            await self.async_subscribe()
            self._is_ready = True

    @callback
    def async_write_entity_states(self) -> bool:
        """Write states for associated SonosEntity instances."""
        async_dispatcher_send(self.hass, f"{SONOS_STATE_UPDATED}-{self.soco.uid}")

    @property
    def available(self) -> bool:
        """Return whether this speaker is available."""
        return self._seen_timer is not None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return information about the device."""
        return {
            "identifiers": {(SONOS_DOMAIN, self.soco.uid)},
            "name": self.zone_name,
            "model": self.model_name.replace("Sonos ", ""),
            "sw_version": self.version,
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            "manufacturer": "Sonos",
            "suggested_area": self.zone_name,
        }

    async def async_subscribe(self) -> bool:
        """Initiate event subscriptions."""
        _LOGGER.debug("Creating subscriptions for %s", self.zone_name)
        try:
            self.async_dispatch_player_reconnected()

            if self._subscriptions:
                raise RuntimeError(
                    f"Attempted to attach subscriptions to player: {self.soco} "
                    f"when existing subscriptions exist: {self._subscriptions}"
                )

            await gather(
                self._subscribe(self.soco.avTransport, self.async_dispatch_media),
                self._subscribe(self.soco.renderingControl, self.async_dispatch_volume),
                self._subscribe(
                    self.soco.contentDirectory, self.async_dispatch_content
                ),
                self._subscribe(
                    self.soco.zoneGroupTopology, self.async_dispatch_groups
                ),
                self._subscribe(
                    self.soco.deviceProperties, self.async_dispatch_properties
                ),
            )
            return True
        except SoCoException as ex:
            _LOGGER.warning("Could not connect %s: %s", self.zone_name, ex)
            return False

    async def _subscribe(
        self, target: SubscriptionBase, sub_callback: Callable
    ) -> None:
        """Create a Sonos subscription."""
        subscription = await target.subscribe(auto_renew=True)
        subscription.callback = sub_callback
        self._subscriptions.append(subscription)

    @callback
    def async_dispatch_media(self, event: SonosEvent | None = None) -> None:
        """Update currently playing media from event."""
        async_dispatcher_send(self.hass, f"{SONOS_MEDIA_UPDATE}-{self.soco.uid}", event)

    @callback
    def async_dispatch_content(self, event: SonosEvent | None = None) -> None:
        """Update available content from event."""
        async_dispatcher_send(
            self.hass, f"{SONOS_CONTENT_UPDATE}-{self.soco.uid}", event
        )

    @callback
    def async_dispatch_volume(self, event: SonosEvent | None = None) -> None:
        """Update volume from event."""
        async_dispatcher_send(
            self.hass, f"{SONOS_VOLUME_UPDATE}-{self.soco.uid}", event
        )

    @callback
    def async_dispatch_properties(self, event: SonosEvent | None = None) -> None:
        """Update properties from event."""
        async_dispatcher_send(
            self.hass, f"{SONOS_PROPERTIES_UPDATE}-{self.soco.uid}", event
        )

    @callback
    def async_dispatch_groups(self, event: SonosEvent | None = None) -> None:
        """Update groups from event."""
        if event and self._poll_timer:
            _LOGGER.debug(
                "Received event, cancelling poll timer for %s", self.zone_name
            )
            self._poll_timer()
            self._poll_timer = None

        async_dispatcher_send(self.hass, SONOS_GROUP_UPDATE, event)

    @callback
    def async_dispatch_player_reconnected(self) -> None:
        """Signal that player has been reconnected."""
        async_dispatcher_send(self.hass, f"{SONOS_PLAYER_RECONNECTED}-{self.soco.uid}")

    async def async_seen(self, soco: SoCo | None = None) -> None:
        """Record that this speaker was seen right now."""
        if soco is not None:
            self.soco = soco

        was_available = self.available
        _LOGGER.debug("Async seen: %s, was_available: %s", self.soco, was_available)

        if self._seen_timer:
            self._seen_timer()

        self._seen_timer = self.hass.helpers.event.async_call_later(
            SEEN_EXPIRE_TIME.total_seconds(), self.async_unseen
        )

        if was_available:
            self.async_write_entity_states()
            return

        self._poll_timer = self.hass.helpers.event.async_track_time_interval(
            async_dispatcher_send(self.hass, f"{SONOS_ENTITY_UPDATE}-{self.soco.uid}"),
            SCAN_INTERVAL,
        )

        if self._is_ready:
            done = await self.async_subscribe()
            if not done:
                assert self._seen_timer is not None
                self._seen_timer()
                await self.async_unseen()

        self.async_write_entity_states()

    async def async_unseen(self) -> None:
        """Make this player unavailable when it was not seen recently."""
        self.async_write_entity_states()

        self._seen_timer = None

        if self._poll_timer:
            self._poll_timer()
            self._poll_timer = None

        for subscription in self._subscriptions:
            await subscription.unsubscribe()

        self._subscriptions = []
