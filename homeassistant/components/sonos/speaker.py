"""Base class for common speaker tasks."""
from __future__ import annotations

from asyncio import gather
import contextlib
import datetime
import logging
from typing import Any, Callable

from pysonos.core import SoCo
from pysonos.events_base import Event as SonosEvent, SubscriptionBase
from pysonos.exceptions import SoCoException

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    dispatcher_connect,
    dispatcher_send,
)
from homeassistant.util import dt as dt_util

from .const import (
    BATTERY_SCAN_INTERVAL,
    PLATFORMS,
    SCAN_INTERVAL,
    SEEN_EXPIRE_TIME,
    SONOS_CONTENT_UPDATE,
    SONOS_CREATE_BATTERY,
    SONOS_CREATE_MEDIA_PLAYER,
    SONOS_ENTITY_CREATED,
    SONOS_ENTITY_UPDATE,
    SONOS_GROUP_UPDATE,
    SONOS_MEDIA_UPDATE,
    SONOS_PLAYER_RECONNECTED,
    SONOS_SEEN,
    SONOS_STATE_UPDATED,
    SONOS_VOLUME_UPDATE,
)

EVENT_CHARGING = {
    "CHARGING": True,
    "NOT_CHARGING": False,
}

_LOGGER = logging.getLogger(__name__)


def fetch_battery_info_or_none(soco: SoCo) -> dict[str, Any] | None:
    """Fetch battery_info from the given SoCo object.

    Returns None if the device doesn't support battery info
    or if the device is offline.
    """
    with contextlib.suppress(ConnectionError, TimeoutError, SoCoException):
        return soco.get_battery_info()


class SonosSpeaker:
    """Representation of a Sonos speaker."""

    def __init__(
        self, hass: HomeAssistant, soco: SoCo, speaker_info: dict[str, Any]
    ) -> None:
        """Initialize a SonosSpeaker."""
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

        self.battery_info: dict[str, Any] | None = None
        self._last_battery_event: datetime.datetime | None = None
        self._battery_poll_timer: Callable | None = None

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

        if (battery_info := fetch_battery_info_or_none(self.soco)) is not None:
            # Battery events can be infrequent, polling is still necessary
            self.battery_info = battery_info
            self._battery_poll_timer = self.hass.helpers.event.track_time_interval(
                self.async_poll_battery, BATTERY_SCAN_INTERVAL
            )
            dispatcher_send(self.hass, SONOS_CREATE_BATTERY, self)
        else:
            self._platforms_ready.update({BINARY_SENSOR_DOMAIN, SENSOR_DOMAIN})

        dispatcher_send(self.hass, SONOS_CREATE_MEDIA_PLAYER, self)

    async def async_handle_new_entity(self, entity_type: str) -> None:
        """Listen to new entities to trigger first subscription."""
        self._platforms_ready.add(entity_type)
        if self._platforms_ready == PLATFORMS:
            await self.async_subscribe()
            self._is_ready = True

    @callback
    def async_write_entity_states(self) -> None:
        """Write states for associated SonosEntity instances."""
        async_dispatcher_send(self.hass, f"{SONOS_STATE_UPDATED}-{self.soco.uid}")

    @property
    def available(self) -> bool:
        """Return whether this speaker is available."""
        return self._seen_timer is not None

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
        self.hass.async_create_task(self.async_update_device_properties(event))

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

    async def async_unseen(self, now: datetime.datetime | None = None) -> None:
        """Make this player unavailable when it was not seen recently."""
        self.async_write_entity_states()

        self._seen_timer = None

        if self._poll_timer:
            self._poll_timer()
            self._poll_timer = None

        for subscription in self._subscriptions:
            await subscription.unsubscribe()

        self._subscriptions = []

    async def async_update_device_properties(self, event: SonosEvent = None) -> None:
        """Update device properties using the provided SonosEvent."""
        if event is None:
            return

        if (more_info := event.variables.get("more_info")) is not None:
            battery_dict = dict(x.split(":") for x in more_info.split(","))
            await self.async_update_battery_info(battery_dict)

        self.async_write_entity_states()

    async def async_update_battery_info(self, battery_dict: dict[str, Any]) -> None:
        """Update battery info using the decoded SonosEvent."""
        self._last_battery_event = dt_util.utcnow()

        is_charging = EVENT_CHARGING[battery_dict["BattChg"]]
        if is_charging == self.charging:
            self.battery_info.update({"Level": int(battery_dict["BattPct"])})
        else:
            if battery_info := await self.hass.async_add_executor_job(
                fetch_battery_info_or_none, self.soco
            ):
                self.battery_info = battery_info

    @property
    def power_source(self) -> str:
        """Return the name of the current power source.

        Observed to be either BATTERY or SONOS_CHARGING_RING or USB_POWER.
        """
        return self.battery_info.get("PowerSource")

    @property
    def charging(self) -> bool:
        """Return the charging status of the speaker."""
        return self.power_source != "BATTERY"

    async def async_poll_battery(self, now: datetime.datetime | None = None) -> None:
        """Poll the device for the current battery state."""
        if not self.available:
            return

        if (
            self._last_battery_event
            and dt_util.utcnow() - self._last_battery_event < BATTERY_SCAN_INTERVAL
        ):
            return

        if battery_info := await self.hass.async_add_executor_job(
            fetch_battery_info_or_none, self.soco
        ):
            self.battery_info = battery_info
            self.async_write_entity_states()
