"""Last motion and last ring image entities for a DoorBird device."""

# These replace the same-named camera entities, which exposed stills through the
# camera UI even though no live video is involved. The legacy camera entities are
# kept to avoid breaking existing dashboards and automations; a follow-up should
# deprecate them via a repair issue once users have had time to migrate.

from dataclasses import dataclass

import aiohttp

from homeassistant.components.image import (
    Image,
    ImageEntity,
    ImageEntityDescription,
    infer_image_type,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData

_TIMEOUT = 15


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
    configured_event_types = {
        event.event_type for event in door_bird_data.door_station.event_descriptions
    }
    async_add_entities(
        DoorBirdLastEventImage(hass, door_bird_data, description)
        for description in IMAGE_DESCRIPTIONS
        if description.doorbird_event_type in configured_event_types
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
        self._matching_events = {
            event.event
            for event in self._door_station.event_descriptions
            if event.event_type == description.doorbird_event_type
        }

    async def async_image(self) -> bytes | None:
        """Return bytes of the last event image."""
        if self._cached_image:
            return self._cached_image.content
        try:
            image_bytes = await self._door_station.device.get_image(
                self._image_url, timeout=_TIMEOUT
            )
        except aiohttp.ClientError as error:
            raise HomeAssistantError(
                f"Error getting image from DoorBird: {error}"
            ) from error
        content_type = infer_image_type(image_bytes) or "image/jpeg"
        self._cached_image = Image(content_type=content_type, content=image_bytes)
        self._attr_content_type = content_type
        return image_bytes

    async def async_added_to_hass(self) -> None:
        """Subscribe to the underlying DoorBird events."""
        await super().async_added_to_hass()
        for event in self._matching_events:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{DOMAIN}_{event}",
                    self._async_handle_event,
                )
            )

    @callback
    def _async_handle_event(self) -> None:
        """Bust the cache and bump the last-updated timestamp on a new event."""
        self._cached_image = None
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()
