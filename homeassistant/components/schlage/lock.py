"""Platform for Schlage lock integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyschlage.code import AccessCode

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LockData, SchlageConfigEntry, SchlageDataUpdateCoordinator
from .entity import SchlageEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SchlageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Schlage WiFi locks based on a config entry."""
    coordinator = config_entry.runtime_data

    def _add_new_locks(locks: dict[str, LockData]) -> None:
        async_add_entities(
            SchlageLockEntity(coordinator=coordinator, device_id=device_id)
            for device_id in locks
        )

    _add_new_locks(coordinator.data.locks)
    coordinator.new_locks_callbacks.append(_add_new_locks)


class SchlageLockEntity(SchlageEntity, LockEntity):
    """Schlage lock entity."""

    _attr_name = None

    def __init__(
        self, coordinator: SchlageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a Schlage Lock."""
        super().__init__(coordinator=coordinator, device_id=device_id)
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.device_id in self.coordinator.data.locks:
            self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        """Update our internal state attributes."""
        self._attr_is_locked = self._lock.is_locked
        self._attr_is_jammed = self._lock.is_jammed
        self._attr_changed_by = self._lock.last_changed_by()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self.hass.async_add_executor_job(self._lock.lock)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self.hass.async_add_executor_job(self._lock.unlock)
        await self.coordinator.async_request_refresh()

    def _validate_code_name(
        self, codes: dict[str, AccessCode] | None, name: str
    ) -> None:
        """Validate that the code name doesn't already exist."""
        if codes and any(code.name.lower() == name.lower() for code in codes.values()):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_name_exists",
            )

    def _validate_code_value(
        self, codes: dict[str, AccessCode] | None, code: str
    ) -> None:
        """Validate that the code value doesn't already exist."""
        if codes and any(
            existing_code.code == code for existing_code in codes.values()
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_code_exists",
            )

    async def add_code(self, name: str, code: str) -> None:
        """Add a lock code."""

        if TYPE_CHECKING:
            assert code is not None

        codes = self._lock.access_codes
        self._validate_code_name(codes, name)
        self._validate_code_value(codes, code)

        access_code = AccessCode(name=name, code=code)
        await self.hass.async_add_executor_job(self._lock.add_access_code, access_code)
        await self.coordinator.async_request_refresh()

    async def delete_code(self, name: str) -> None:
        """Delete a lock code."""
        codes = self._lock.access_codes
        if not codes:
            return

        code_id_to_delete = next(
            (
                code_id
                for code_id, code_data in codes.items()
                if code_data.name.lower() == name.lower()
            ),
            None,
        )

        if not code_id_to_delete:
            return

        if self._lock.access_codes:
            await self.hass.async_add_executor_job(codes[code_id_to_delete].delete)
            await self.coordinator.async_request_refresh()

    async def get_codes(self) -> ServiceResponse:
        """Get lock codes."""

        if self._lock.access_codes:
            return {
                code: {
                    "name": self._lock.access_codes[code].name,
                    "code": self._lock.access_codes[code].code,
                }
                for code in self._lock.access_codes
            }
        return {}
