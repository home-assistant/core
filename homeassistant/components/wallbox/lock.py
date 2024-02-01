"""Home Assistant component for accessing the Wallbox Portal API. The lock component creates a lock entity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGER_DATA_KEY,
    CHARGER_LOCKED_UNLOCKED_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    DOMAIN,
)
from .coordinator import InvalidAuth, WallboxCoordinator
from .entity import WallboxEntity

LOCK_TYPES: dict[str, LockEntityDescription] = {
    CHARGER_LOCKED_UNLOCKED_KEY: LockEntityDescription(
        key=CHARGER_LOCKED_UNLOCKED_KEY,
        translation_key="lock",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox lock entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Check if the user is authorized to lock, if so, add lock component
    try:
        await coordinator.async_set_lock_unlock(
            coordinator.data[CHARGER_LOCKED_UNLOCKED_KEY]
        )
    except InvalidAuth:
        return
    except ConnectionError as exc:
        raise PlatformNotReady from exc

    async_add_entities(
        [
            WallboxLock(coordinator, description)
            for ent in coordinator.data
            if (description := LOCK_TYPES.get(ent))
        ]
    )


class WallboxLock(WallboxEntity, LockEntity):
    """Representation of a wallbox lock."""

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        description: LockEntityDescription,
    ) -> None:
        """Initialize a Wallbox lock."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def is_locked(self) -> bool:
        """Return the status of the lock."""
        return self.coordinator.data[CHARGER_LOCKED_UNLOCKED_KEY]  # type: ignore[no-any-return]

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock charger."""
        await self.coordinator.async_set_lock_unlock(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock charger."""
        await self.coordinator.async_set_lock_unlock(False)
