"""Image platform for the UniFi Access integration."""

from __future__ import annotations

from datetime import UTC, datetime

from unifi_access_api import Door

from homeassistant.components.image import ImageEntity
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up image entities for UniFi Access doors."""
    coordinator = entry.runtime_data
    async_add_entities(
        UnifiAccessDoorImageEntity(coordinator, hass, entry.data[CONF_VERIFY_SSL], door)
        for door in coordinator.data.doors.values()
    )


class UnifiAccessDoorImageEntity(UnifiAccessEntity, ImageEntity):
    """Image entity for a UniFi Access door thumbnail."""

    _attr_translation_key = "door_thumbnail"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        hass: HomeAssistant,
        verify_ssl: bool,
        door: Door,
    ) -> None:
        """Initialize UniFi Access door image entity."""
        # Explicit __init__ calls required: ImageEntity.__init__ has a
        # different signature (hass, verify_ssl) that is incompatible
        # with the cooperative super().__init__ chain.
        UnifiAccessEntity.__init__(self, coordinator, door, "thumbnail")
        ImageEntity.__init__(self, hass, verify_ssl)
        if thumbnail := coordinator.data.door_thumbnails.get(door.id):
            self._attr_image_last_updated = datetime.fromtimestamp(
                thumbnail.door_thumbnail_last_update, tz=UTC
            )

    async def async_image(self) -> bytes | None:
        """Return the door thumbnail image bytes."""
        if thumbnail := self.coordinator.data.door_thumbnails.get(self._door_id):
            return await self.coordinator.client.get_thumbnail(thumbnail.url)
        return None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if thumbnail := self.coordinator.data.door_thumbnails.get(self._door_id):
            self._attr_image_last_updated = datetime.fromtimestamp(
                thumbnail.door_thumbnail_last_update, tz=UTC
            )
        super()._handle_coordinator_update()
