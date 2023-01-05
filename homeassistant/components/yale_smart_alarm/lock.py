"""Lock for Yale Alarm."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE, CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_LOCK_CODE_DIGITS,
    COORDINATOR,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
    YALE_ALL_ERRORS,
)
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale lock entry."""

    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    code_format = entry.options.get(CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS)

    async_add_entities(
        YaleDoorlock(coordinator, data, code_format)
        for data in coordinator.data["locks"]
    )


class YaleDoorlock(YaleEntity, LockEntity):
    """Representation of a Yale doorlock."""

    def __init__(
        self, coordinator: YaleDataUpdateCoordinator, data: dict, code_format: int
    ) -> None:
        """Initialize the Yale Lock Device."""
        super().__init__(coordinator, data)
        self._attr_code_format = f"^\\d{code_format}$"
        self.lock_name: str = data["name"]

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send unlock command."""
        code: str | None = kwargs.get(
            ATTR_CODE, self.coordinator.entry.options.get(CONF_CODE)
        )
        return await self.async_set_lock("unlocked", code)

    async def async_lock(self, **kwargs: Any) -> None:
        """Send lock command."""
        return await self.async_set_lock("locked", None)

    async def async_set_lock(self, command: str, code: str | None) -> None:
        """Set lock."""
        if TYPE_CHECKING:
            assert self.coordinator.yale, "Connection to API is missing"

        try:
            get_lock = await self.hass.async_add_executor_job(
                self.coordinator.yale.lock_api.get, self.lock_name
            )
            if command == "locked":
                lock_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.lock_api.close_lock,
                    get_lock,
                )
            if command == "unlocked":
                lock_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.lock_api.open_lock, get_lock, code
                )
        except YALE_ALL_ERRORS as error:
            raise HomeAssistantError(
                f"Could not set lock for {self.lock_name}: {error}"
            ) from error

        if lock_state:
            self.coordinator.data["lock_map"][self._attr_unique_id] = command
            self.async_write_ha_state()
            return
        raise HomeAssistantError("Could not set lock, check system ready for lock.")

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return bool(self.coordinator.data["lock_map"][self._attr_unique_id] == "locked")
