"""Support for DoorBird devices."""

from collections import defaultdict
from dataclasses import dataclass
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from doorbirdpy import (
    DoorBird,
    DoorBirdScheduleEntry,
    DoorBirdScheduleEntryOutput,
    DoorBirdScheduleEntrySchedule,
)
from propcache.api import cached_property

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import get_url
from homeassistant.util import dt as dt_util, slugify

from .const import (
    API_URL,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_EVENT_TYPES,
    HTTP_EVENT_TYPE,
    MAX_WEEKDAY,
    MIN_WEEKDAY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DoorbirdEvent:
    """Describes a doorbird event."""

    event: str
    event_type: str


@dataclass(slots=True)
class DoorbirdEventConfig:
    """Describes the configuration of doorbird events."""

    events: list[DoorbirdEvent]
    schedule: list[DoorBirdScheduleEntry]
    unconfigured_favorites: defaultdict[str, list[str]]


class ConfiguredDoorBird:
    """Attach additional information to pass along with configured device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: DoorBird,
        name: str | None,
        custom_url: str | None,
        token: str,
        event_entity_ids: dict[str, str],
    ) -> None:
        """Initialize configured device."""
        self._hass = hass
        self._name = name
        self._device = device
        self._custom_url = custom_url
        self._token = token
        self._event_entity_ids = event_entity_ids
        # Raw events, ie "doorbell" or "motion"
        self.events: list[str] = []
        # Event names, ie "doorbird_1234_doorbell" or "doorbird_1234_motion"
        self.door_station_events: list[str] = []
        self.event_descriptions: list[DoorbirdEvent] = []
        # The event names that refresh each image, by image event type, and the
        # configured events the device will actually call. Both are resolved
        # here, since only this class knows which favorites registered.
        self.image_event_names: dict[str, list[str]] = {}
        self._callable_events: set[str] = set()

    def update_events(self, events: list[str]) -> None:
        """Update the doorbird events."""
        # Clearing the options field yields [""], since it splits an empty
        # string, and an empty name registers a webhook nothing can call.
        self.events = [event for event in events if event]
        self.door_station_events = [
            self._get_event_name(event) for event in self.events
        ]

    @cached_property
    def name(self) -> str | None:
        """Get custom device name."""
        return self._name

    @cached_property
    def device(self) -> DoorBird:
        """Get the configured device."""
        return self._device

    @cached_property
    def custom_url(self) -> str | None:
        """Get custom url for device."""
        return self._custom_url

    @cached_property
    def token(self) -> str:
        """Get token for device."""
        return self._token

    def _get_hass_url(self) -> str:
        """Get the Home Assistant URL for this device."""
        if custom_url := self.custom_url:
            return custom_url
        return get_url(self._hass, prefer_external=False)

    async def async_register_events(self) -> None:
        """Register events on device."""
        if not self.door_station_events:
            # The config entry might not have any events configured yet
            self._callable_events = set()
            self._async_resolve_image_events()
            return
        http_fav = await self._async_register_events()
        event_config = await self._async_get_event_config(http_fav)
        _LOGGER.debug("%s: Event config: %s", self.name, event_config)
        if event_config.unconfigured_favorites:
            await self._configure_unconfigured_favorites(event_config)
            event_config = await self._async_get_event_config(http_fav)
        self.event_descriptions = event_config.events
        if event_config.schedule:
            # With the schedule API the device reports which input calls each
            # favorite, so one it does not describe it will never call: the
            # schedule write was rejected, or a renamed event has not been
            # assigned to an input in the DoorBird app yet.
            self._callable_events.intersection_update(
                event.event for event in event_config.events
            )
        # Only the names the device will actually call can refresh an image.
        self._async_resolve_image_events()

    async def _configure_unconfigured_favorites(
        self, event_config: DoorbirdEventConfig
    ) -> None:
        """Configure unconfigured favorites."""
        for entry in event_config.schedule:
            modified_schedule = False
            for identifier in event_config.unconfigured_favorites.get(entry.input, ()):
                schedule = DoorBirdScheduleEntrySchedule()
                schedule.add_weekday(MIN_WEEKDAY, MAX_WEEKDAY)
                entry.output.append(
                    DoorBirdScheduleEntryOutput(
                        enabled=True,
                        event=HTTP_EVENT_TYPE,
                        param=identifier,
                        schedule=schedule,
                    )
                )
                modified_schedule = True

            if modified_schedule:
                update_ok, code = await self.device.change_schedule(entry)
                if not update_ok:
                    _LOGGER.error(
                        "Unable to update schedule entry %s to %s. Error code: %s",
                        self.name,
                        entry.export,
                        code,
                    )

    async def _async_register_events(self) -> dict[str, Any]:
        """Register events on device."""
        hass_url = self._get_hass_url()
        http_fav = await self._async_get_http_favorites()
        self._callable_events = set(self.door_station_events)
        # Note that a list is built here to ensure all events are registered
        # and the any() below does not short circuit.
        added = [
            await self._async_register_event(hass_url, event, http_fav)
            for event in self.door_station_events
        ]
        if any(added):
            # If any events were registered, get the updated favorites
            http_fav = await self._async_get_http_favorites()

        return http_fav

    async def _async_get_event_config(
        self, http_fav: dict[str, dict[str, Any]]
    ) -> DoorbirdEventConfig:
        """Get events and unconfigured favorites from http favorites."""
        device = self.device
        events: list[DoorbirdEvent] = []
        unconfigured_favorites: defaultdict[str, list[str]] = defaultdict(list)
        try:
            schedule = await device.schedule()
        except ClientResponseError as ex:
            if ex.status == HTTPStatus.NOT_FOUND:
                # D301 models do not support schedules
                return DoorbirdEventConfig(events, [], unconfigured_favorites)
            raise
        favorite_input_type = {
            output.param: entry.input
            for entry in schedule
            for output in entry.output
            # A disabled output is one the device will not call, so the event
            # is not reported and nothing subscribes to it.
            if output.event == HTTP_EVENT_TYPE and output.enabled
        }
        default_event_types = {
            self._get_event_name(event): event_type
            for event, event_type in DEFAULT_EVENT_TYPES
        }
        hass_url = self._get_hass_url()
        for identifier, data in http_fav.items():
            title: str | None = data.get("title")
            if not title or not title.startswith("Home Assistant"):
                continue
            value: str | None = data.get("value")
            if not value or not value.startswith(hass_url):
                continue  # Not our favorite - different HA instance or stale
            event = title.partition("(")[2].strip(")")
            if input_type := favorite_input_type.get(identifier):
                events.append(DoorbirdEvent(event, input_type))
            elif input_type := default_event_types.get(event):
                unconfigured_favorites[input_type].append(identifier)

        return DoorbirdEventConfig(events, schedule, unconfigured_favorites)

    @cached_property
    def slug(self) -> str:
        """Get device slug."""
        return slugify(self._name)

    @callback
    def _async_resolve_image_events(self) -> None:
        """Resolve which event names refresh each image.

        Only events the device will actually call are usable, so a favorite that
        failed to register leaves its image without one and the camera it
        replaces stays. Each callable event belongs to one image: the type the
        schedule gives it, the type its default name implies, or the last ring
        image when the user renamed it and nothing can classify it.
        """
        described = {event.event: event.event_type for event in self.event_descriptions}
        default_types = dict(DEFAULT_EVENT_TYPES)
        by_type: dict[str, list[str]] = {
            event_type: [] for _, event_type in DEFAULT_EVENT_TYPES
        }
        for event, event_name in zip(
            self.events, self.door_station_events, strict=True
        ):
            if event_name not in self._callable_events:
                continue
            event_type = described.get(event_name) or default_types.get(
                event, DEFAULT_DOORBELL_EVENT
            )
            if event_type in by_type:
                by_type[event_type].append(event_name)
        self.image_event_names = by_type

    def _get_event_name(self, event: str) -> str:
        return f"{self.slug}_{event}"

    async def _async_get_http_favorites(self) -> dict[str, dict[str, Any]]:
        """Get the HTTP favorites from the device."""
        return (await self.device.favorites()).get(HTTP_EVENT_TYPE) or {}

    async def _async_register_event(
        self, hass_url: str, event: str, http_fav: dict[str, dict[str, Any]]
    ) -> bool:
        """Register an event.

        Returns True if the event was registered, False if
        the event was already registered or registration failed.
        """
        url = f"{hass_url}{API_URL}/{event}?token={self._token}"
        _LOGGER.debug("Registering URL %s for event %s", url, event)
        # If its already registered, don't register it again
        if any(fav["value"] == url for fav in http_fav.values()):
            _LOGGER.debug("URL already registered for %s", event)
            return False

        if not await self.device.change_favorite(
            HTTP_EVENT_TYPE, f"Home Assistant ({event})", url
        ):
            _LOGGER.warning(
                'Unable to set favorite URL "%s". Event "%s" will not fire',
                url,
                event,
            )
            self._callable_events.discard(event)
            return False

        _LOGGER.debug("Successfully registered URL for %s on %s", event, self.name)
        return True

    def get_event_data(self, event: str) -> dict[str, str | None]:
        """Get data to pass along with HA event."""
        return {
            "timestamp": dt_util.utcnow().isoformat(),
            "live_video_url": self._device.live_video_url,
            "live_image_url": self._device.live_image_url,
            "rtsp_live_video_url": self._device.rtsp_live_video_url,
            "html5_viewer_url": self._device.html5_viewer_url,
            ATTR_ENTITY_ID: self._event_entity_ids.get(event),
        }


async def async_reset_device_favorites(door_station: ConfiguredDoorBird) -> None:
    """Handle clearing favorites on device."""
    door_bird = door_station.device
    favorites = await door_bird.favorites()
    for favorite_type, favorite_ids in favorites.items():
        for favorite_id in favorite_ids:
            await door_bird.delete_favorite(favorite_type, favorite_id)
    await door_station.async_register_events()
