"""Image platform for the UniFi Access integration."""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from unifi_access_api import Door, UnifiAccessError

from homeassistant.components.image import ImageEntity
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up image entities for UniFi Access doors."""
    coordinator = entry.runtime_data
    added_doors: set[str] = set()

    @callback
    def _async_add_new_doors() -> None:
        new_door_ids = sorted(set(coordinator.data.door_thumbnails) - added_doors)
        if not new_door_ids:
            return
        async_add_entities(
            UnifiAccessDoorImageEntity(
                coordinator,
                hass,
                entry.data[CONF_VERIFY_SSL],
                coordinator.data.doors[door_id],
            )
            for door_id in new_door_ids
        )
        added_doors.update(new_door_ids)

    _async_add_new_doors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_doors))


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
            try:
                return await self.coordinator.client.get_thumbnail(thumbnail.url)
            except UnifiAccessError as err:
                _LOGGER.warning(
                    "Failed to fetch thumbnail for door %s: %s",
                    self._door_id,
                    err,
                )
        return None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if thumbnail := self.coordinator.data.door_thumbnails.get(self._door_id):
            self._attr_image_last_updated = datetime.fromtimestamp(
                thumbnail.door_thumbnail_last_update, tz=UTC
            )
        super()._handle_coordinator_update()
