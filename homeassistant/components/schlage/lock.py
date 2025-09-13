"""Platform for Schlage lock integration."""

from __future__ import annotations

from typing import Any

from pyschlage.code import AccessCode
import voluptuous as vol

from homeassistant.components.lock import LockEntity
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SERVICE_ADD_CODE, SERVICE_DELETE_CODE, SERVICE_GET_CODES
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

    # Custom services
    def _validate_code_name(codes: dict[str, AccessCode] | None, name: str) -> None:
        """Validate that the code name doesn't already exist."""
        if codes and any(code.name.lower() == name.lower() for code in codes.values()):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_name_exists",
            )

    def _validate_code_value(codes: dict[str, AccessCode] | None, code: str) -> None:
        """Validate that the code value doesn't already exist."""
        if codes and any(
            existing_code.code == code for existing_code in codes.values()
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_code_exists",
            )

    async def _add_code(entity: SchlageLockEntity, calls: ServiceCall) -> None:
        """Add a lock code."""
        name = calls.data.get("name")
        code = calls.data.get("code")

        # name is required by voluptuous, the following is just to satisfy type
        # checker, it should never be None
        if name is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_name_required",
            )  # pragma: no cover

        # code is required by voluptuous, the following is just to satisfy type
        # checker, it should never be None
        if code is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_code_required",
            )  # pragma: no cover

        codes = entity._lock.access_codes  # noqa: SLF001
        _validate_code_name(codes, name)
        _validate_code_value(codes, code)

        access_code = AccessCode(name=name, code=code)
        await hass.async_add_executor_job(entity._lock.add_access_code, access_code)  # noqa: SLF001
        await coordinator.async_request_refresh()

    async def _delete_code(entity: SchlageLockEntity, calls: ServiceCall) -> None:
        """Delete a lock code."""
        name = calls.data.get("name")

        # name is required by voluptuous, the following is just to satisfy type
        # checker, it should never be None
        if name is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_name_required",
            )  # pragma: no cover

        codes = entity._lock.access_codes  # noqa: SLF001
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

        if entity._lock.access_codes:  # noqa: SLF001
            await hass.async_add_executor_job(
                entity._lock.access_codes[code_id_to_delete].delete  # noqa: SLF001
            )
            await coordinator.async_request_refresh()

    async def _get_codes(
        entity: SchlageLockEntity, calls: ServiceCall
    ) -> ServiceResponse:
        """Get lock codes."""

        if entity._lock.access_codes:  # noqa: SLF001
            return {
                code: {
                    "name": entity._lock.access_codes[code].name,  # noqa: SLF001
                    "code": entity._lock.access_codes[code].code,  # noqa: SLF001
                }
                for code in entity._lock.access_codes  # noqa: SLF001
            }
        return {}

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        name=SERVICE_ADD_CODE,
        schema={
            vol.Required("name"): cv.string,
            vol.Required("code"): cv.matches_regex(r"^\d{4,8}$"),
        },
        func=_add_code,
    )

    platform.async_register_entity_service(
        name=SERVICE_DELETE_CODE,
        schema={
            vol.Required("name"): cv.string,
        },
        func=_delete_code,
    )

    platform.async_register_entity_service(
        name=SERVICE_GET_CODES,
        schema=None,
        func=_get_codes,
        supports_response=SupportsResponse.ONLY,
    )


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
