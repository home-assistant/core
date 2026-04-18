"""Button platform for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door, UnifiAccessError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access button entities."""
    coordinator = entry.runtime_data
    added_doors: set[str] = set()

    @callback
    def _async_add_new_doors() -> None:
        new_door_ids = sorted(set(coordinator.data.doors) - added_doors)
        if not new_door_ids:
            return
        async_add_entities(
            UnifiAccessUnlockButton(coordinator, coordinator.data.doors[door_id])
            for door_id in new_door_ids
        )
        added_doors.update(new_door_ids)

    _async_add_new_doors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_doors))


class UnifiAccessUnlockButton(UnifiAccessEntity, ButtonEntity):
    """Representation of a UniFi Access door unlock button."""

    _attr_translation_key = "unlock"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, door, "unlock")

    async def async_press(self) -> None:
        """Unlock the door."""
        try:
            await self.coordinator.client.unlock_door(self._door_id)
        except UnifiAccessError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
            ) from err
