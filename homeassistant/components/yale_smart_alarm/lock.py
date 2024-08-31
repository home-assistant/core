"""Lock for Yale Alarm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YaleConfigEntry
from .const import (
    CONF_LOCK_CODE_DIGITS,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
    YALE_ALL_ERRORS,
)
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: YaleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale lock entry."""

    coordinator = entry.runtime_data
    code_format = entry.options.get(CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS)

    async_add_entities(
        YaleDoorlock(coordinator, data, code_format)
        for data in coordinator.data["locks"]
    )


class YaleDoorlock(YaleEntity, LockEntity):
    """Representation of a Yale doorlock."""

    _attr_name = None

    def __init__(
        self, coordinator: YaleDataUpdateCoordinator, data: dict, code_format: int
    ) -> None:
        """Initialize the Yale Lock Device."""
        super().__init__(coordinator, data)
        self._attr_code_format = rf"^\d{{{code_format}}}$"
        self.lock_name: str = data["name"]

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send unlock command."""
        code: str | None = kwargs.get(ATTR_CODE)
        return await self.async_set_lock("unlocked", code)

    async def async_lock(self, **kwargs: Any) -> None:
        """Send lock command."""
        return await self.async_set_lock("locked", None)

    async def async_set_lock(self, command: str, code: str | None) -> None:
        """Set lock."""
        if TYPE_CHECKING:
            assert self.coordinator.yale, "Connection to API is missing"
        if command == "unlocked" and not code:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_code",
            )

        try:
            get_lock = await self.hass.async_add_executor_job(
                self.coordinator.yale.lock_api.get, self.lock_name
            )
            if get_lock and command == "locked":
                lock_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.lock_api.close_lock,
                    get_lock,
                )
            if code and get_lock and command == "unlocked":
                lock_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.lock_api.open_lock, get_lock, code
                )
        except YALE_ALL_ERRORS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_lock",
                translation_placeholders={
                    "name": self.lock_name,
                    "error": str(error),
                },
            ) from error

        if lock_state:
            self.coordinator.data["lock_map"][self._attr_unique_id] = command
            self.async_write_ha_state()
            return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="could_not_change_lock",
        )

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return bool(self.coordinator.data["lock_map"][self._attr_unique_id] == "locked")
