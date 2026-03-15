"""Button platform for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door, UnifiAccessError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
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
    async_add_entities(
        UnifiAccessUnlockButton(coordinator, door)
        for door in coordinator.data.doors.values()
    )


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
