"""Support for DoorBird devices."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
import logging
from typing import Any

from doorbirdpy import (
    DoorBird,
    DoorBirdScheduleEntry,
    DoorBirdScheduleEntryOutput,
    DoorBirdScheduleEntrySchedule,
)

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url
from homeassistant.util import dt as dt_util, slugify

from .const import API_URL, DEFAULT_EVENT_TYPES, HTTP_EVENT_TYPE

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
        device: DoorBird,
        name: str | None,
        custom_url: str | None,
        token: str,
        event_entity_ids: dict[str, str],
    ) -> None:
        """Initialize configured device."""
        self._name = name
        self._device = device
        self._custom_url = custom_url
        self._token = token
        self._event_entity_ids = event_entity_ids
        self.events: list[str] = []
        self.door_station_events: list[str] = []
        self.event_descriptions: list[DoorbirdEvent] = []

    def update_events(self, events: list[str]) -> None:
        """Update the doorbird events."""
        self.events = events
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

    async def async_register_events(self, hass: HomeAssistant) -> None:
        """Register events on device."""
        device = self.device
        # Override url if another is specified in the configuration
        if custom_url := self.custom_url:
            hass_url = custom_url
        else:
            # Get the URL of this server
            hass_url = get_url(hass, prefer_external=False)

        if not self.door_station_events:
            # User may not have permission to get the favorites
            return

        favorites = await device.favorites()
        http_fav = favorites.get(HTTP_EVENT_TYPE) or {}
        favorites_changed = False
        for event in self.door_station_events:
            if await self._async_register_event(hass_url, event, favs=favorites):
                _LOGGER.info(
                    "Successfully registered URL for %s on %s", event, self.name
                )
                favorites_changed = True

        if favorites_changed:
            http_fav = (await device.favorites()).get(HTTP_EVENT_TYPE) or {}

        event_config = await self._async_get_event_config(http_fav)
        if unconfigured_favs := event_config.unconfigured_favorites:
            for entry in event_config.schedule:
                modified_schedule = False
                for identifier in unconfigured_favs.get(entry.input, ()):
                    schedule = DoorBirdScheduleEntrySchedule()
                    schedule.add_weekday(104400, 104399)
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
                    update_ok, code = await device.change_schedule(entry)
                    if not update_ok:
                        _LOGGER.error(
                            "Unable to update schedule entry %s to %s. Error code: %s",
                            self.name,
                            entry.export,
                            code,
                        )

            event_config = await self._async_get_event_config(http_fav)

        self.event_descriptions = event_config.events

    async def _async_get_event_config(
        self, http_fav: dict[str, dict[str, Any]]
    ) -> DoorbirdEventConfig:
        """Get events and unconfigured favorites from http favorites."""
        device = self.device
        schedule = await device.schedule()
        favorite_input_type: dict[str, str] = {
            output.param: entry.input
            for entry in schedule
            for output in entry.output
            if output.event == HTTP_EVENT_TYPE
        }
        events: list[DoorbirdEvent] = []
        unconfigured_favorites: defaultdict[str, list[str]] = defaultdict(list)
        default_event_types = {
            self._get_event_name(event): event_type
            for event, event_type in DEFAULT_EVENT_TYPES
        }
        for identifier, data in http_fav.items():
            title: str | None = data.get("title")
            if not title or not title.startswith("Home Assistant"):
                continue
            event = title.split("(")[1].strip(")")
            if input_type := favorite_input_type.get(identifier):
                events.append(DoorbirdEvent(event, input_type))
            elif input_type := default_event_types.get(event):
                unconfigured_favorites[input_type].append(identifier)

        return DoorbirdEventConfig(events, schedule, unconfigured_favorites)

    @cached_property
    def slug(self) -> str:
        """Get device slug."""
        return slugify(self._name)

    def _get_event_name(self, event: str) -> str:
        return f"{self.slug}_{event}"

    async def _async_register_event(
        self, hass_url: str, event: str, favs: dict[str, Any] | None = None
    ) -> bool:
        """Add a schedule entry in the device for a sensor."""
        url = f"{hass_url}{API_URL}/{event}?token={self._token}"

        # Register HA URL as webhook if not already, then get the ID
        if await self.async_webhook_is_registered(url, favs=favs):
            return True

        await self.device.change_favorite(
            HTTP_EVENT_TYPE, f"Home Assistant ({event})", url
        )
        if not await self.async_webhook_is_registered(url):
            _LOGGER.warning(
                'Unable to set favorite URL "%s". Event "%s" will not fire',
                url,
                event,
            )
            return False
        return True

    async def async_webhook_is_registered(
        self, url: str, favs: dict[str, Any] | None = None
    ) -> bool:
        """Return whether the given URL is registered as a device favorite."""
        return await self.async_get_webhook_id(url, favs) is not None

    async def async_get_webhook_id(
        self, url: str, favs: dict[str, Any] | None = None
    ) -> str | None:
        """Return the device favorite ID for the given URL.

        The favorite must exist or there will be problems.
        """
        favs = favs if favs else await self.device.favorites()
        http_fav: dict[str, dict[str, Any]] = favs.get(HTTP_EVENT_TYPE) or {}
        for fav_id, data in http_fav.items():
            if data["value"] == url:
                return fav_id
        return None

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


async def async_reset_device_favorites(
    hass: HomeAssistant, door_station: ConfiguredDoorBird
) -> None:
    """Handle clearing favorites on device."""
    door_bird = door_station.device
    favorites = await door_bird.favorites()
    for favorite_type, favorite_ids in favorites.items():
        for favorite_id in favorite_ids:
            await door_bird.delete_favorite(favorite_type, favorite_id)
