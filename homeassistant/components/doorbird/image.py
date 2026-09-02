"""Last motion and last ring image entities for a DoorBird device."""

from dataclasses import dataclass
from typing import override

import aiohttp

from homeassistant.components.image import (
    Image,
    ImageEntity,
    ImageEntityDescription,
    infer_image_type,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_EVENT_TYPES,
    DOMAIN,
    SIGNAL_EVENTS_UPDATED,
)
from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData


@dataclass(frozen=True, kw_only=True)
class DoorBirdImageEntityDescription(ImageEntityDescription):
    """Describes a DoorBird image entity."""

    doorbird_event_type: str


IMAGE_DESCRIPTIONS: tuple[DoorBirdImageEntityDescription, ...] = (
    DoorBirdImageEntityDescription(
        key="last_motion",
        translation_key="last_motion",
        doorbird_event_type="motion",
    ),
    DoorBirdImageEntityDescription(
        key="last_ring",
        translation_key="last_ring",
        doorbird_event_type="doorbell",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DoorBirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DoorBird image platform."""
    door_bird_data = config_entry.runtime_data
    async_add_entities(
        DoorBirdLastEventImage(hass, door_bird_data, description)
        for description in IMAGE_DESCRIPTIONS
    )


class DoorBirdLastEventImage(ImageEntity, DoorBirdEntity):
    """An image of the last motion or last ring on a DoorBird device."""

    entity_description: DoorBirdImageEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        door_bird_data: DoorBirdData,
        description: DoorBirdImageEntityDescription,
    ) -> None:
        """Initialize the image entity."""
        ImageEntity.__init__(self, hass)
        DoorBirdEntity.__init__(self, door_bird_data)
        self.entity_description = description
        self._attr_unique_id = f"{self._mac_addr}_{description.key}"
        history_type = (
            "doorbell"
            if description.doorbird_event_type == "doorbell"
            else "motionsensor"
        )
        self._image_url = self._door_station.device.history_image_url(1, history_type)
        self._subscribed_event_names: list[str] = []
        self._event_unsubscribes: list[CALLBACK_TYPE] = []

    @property
    def _matching_event_names(self) -> list[str]:
        """Return the event names that refresh this image.

        Resolved on each use because the options listener replaces the
        descriptions without reloading the platform. Models without the
        schedule API report no descriptions at all, so fall back to the
        configured events to keep the image refreshing: the ones this type
        names, or every unclassifiable one when the user renamed them.
        """
        event_type = self.entity_description.doorbird_event_type
        door_station = self._door_station
        # The device keeps the favorites and schedule entries of a deconfigured
        # event, so the descriptions can still name one that was removed.
        configured = set(door_station.door_station_events)
        described_names = [
            event.event
            for event in door_station.event_descriptions
            if event.event_type == event_type and event.event in configured
        ]

        # An event the schedule attributes to either image is spoken for, so the
        # fallback only covers the configured events it left over.
        described = {event.event for event in door_station.event_descriptions}
        classifiable = {event for event, _ in DEFAULT_EVENT_TYPES}
        own_events = {
            event
            for event, default_type in DEFAULT_EVENT_TYPES
            if default_type == event_type
        }
        # A renamed event cannot be attributed to either image, so the doorbell
        # one takes it: without this the replacement never refreshes, while the
        # deprecated cameras polled on a timer regardless of the event names.
        takes_unclassifiable = event_type == DEFAULT_DOORBELL_EVENT
        return described_names + [
            event_name
            for event, event_name in zip(
                door_station.events, door_station.door_station_events, strict=True
            )
            if event_name not in described
            and (
                event in own_events
                or (takes_unclassifiable and event not in classifiable)
            )
        ]

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of the last event image."""
        if self._cached_image:
            return self._cached_image.content
        try:
            # No explicit timeout here — the image framework wraps async_image() in its
            # own asyncio.timeout(IMAGE_TIMEOUT) and raises HTTP 500 on expiry.
            image_bytes = await self._door_station.device.get_image(self._image_url)
        except aiohttp.ClientError as error:
            raise HomeAssistantError(
                f"Error getting image from DoorBird: {error}"
            ) from error
        content_type = infer_image_type(image_bytes)
        if content_type is None:
            raise HomeAssistantError("DoorBird returned an unrecognized image")
        self._cached_image = Image(content_type=content_type, content=image_bytes)
        self._attr_content_type = content_type
        return image_bytes

    @callback
    def _async_subscribe_events(self) -> None:
        """Map and subscribe to the events that currently refresh this image."""
        event_to_entity_id = self._door_bird_data.event_entity_ids
        self._subscribed_event_names = self._matching_event_names
        for event_name in self._subscribed_event_names:
            event_to_entity_id[event_name] = self.entity_id
            self._event_unsubscribes.append(
                async_dispatcher_connect(
                    self.hass,
                    f"{DOMAIN}_{event_name}",
                    self._async_handle_event,
                )
            )

    @callback
    def _async_unsubscribe_events(self) -> None:
        """Drop the current mappings and subscriptions."""
        event_to_entity_id = self._door_bird_data.event_entity_ids
        for event_name in self._subscribed_event_names:
            # Another image may already have claimed the event, if a refresh
            # moved it between the doorbell and motion types.
            if event_to_entity_id.get(event_name) == self.entity_id:
                del event_to_entity_id[event_name]
        while self._event_unsubscribes:
            self._event_unsubscribes.pop()()

    @callback
    def _async_handle_events_updated(self) -> None:
        """Resubscribe after the configured events changed."""
        self._async_unsubscribe_events()
        self._async_subscribe_events()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the underlying DoorBird events."""
        await super().async_added_to_hass()
        self._async_subscribe_events()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_EVENTS_UPDATED}_{self._mac_addr}",
                self._async_handle_events_updated,
            )
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from events."""
        self._async_unsubscribe_events()
        await super().async_will_remove_from_hass()

    @callback
    def _async_handle_event(self) -> None:
        """Bust the cache and bump the last-updated timestamp on a new event."""
        self._cached_image = None
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()
