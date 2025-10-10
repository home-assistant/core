"""Volvo locks."""

from dataclasses import dataclass
import logging
from typing import Any, cast

from volvocarsapi.models import VolvoApiException, VolvoCarsApiBaseModel, VolvoCarsValue

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VolvoConfigEntry
from .entity import VolvoEntity, VolvoEntityDescription

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VolvoLockDescription(VolvoEntityDescription, LockEntityDescription):
    """Describes a Volvo lock entity."""

    api_lock_value: str = "LOCKED"
    api_unlock_value: str = "UNLOCKED"
    lock_command: str
    unlock_command: str
    required_command_key: str


_DESCRIPTIONS: tuple[VolvoLockDescription, ...] = (
    VolvoLockDescription(
        key="lock",
        api_field="centralLock",
        lock_command="lock",
        unlock_command="unlock",
        required_command_key="LOCK",
    ),
    VolvoLockDescription(
        key="lock_reduced_guard",
        api_field="centralLock",
        lock_command="lock-reduced-guard",
        unlock_command="unlock",
        required_command_key="LOCK_REDUCED_GUARD",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up locks."""
    coordinators = entry.runtime_data.interval_coordinators
    async_add_entities(
        [
            VolvoLock(coordinator, description)
            for coordinator in coordinators
            for description in _DESCRIPTIONS
            if description.required_command_key
            in entry.runtime_data.context.supported_commands
            and description.api_field in coordinator.data
        ]
    )


class VolvoLock(VolvoEntity, LockEntity):
    """Volvo lock."""

    entity_description: VolvoLockDescription

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the car."""
        await self._async_handle_command(self.entity_description.lock_command, True)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the car."""
        await self._async_handle_command(self.entity_description.unlock_command, False)

    def _update_state(self, api_field: VolvoCarsApiBaseModel | None) -> None:
        """Update the state of the entity."""
        assert isinstance(api_field, VolvoCarsValue)
        self._attr_is_locked = api_field.value == "LOCKED"

    async def _async_handle_command(self, command: str, locked: bool) -> None:
        _LOGGER.debug("Lock '%s' is %s", command, "locked" if locked else "unlocked")
        if locked:
            self._attr_is_locking = True
        else:
            self._attr_is_unlocking = True
        self.async_write_ha_state()

        try:
            result = await self.coordinator.context.api.async_execute_command(command)
        except VolvoApiException as ex:
            _LOGGER.debug("Lock '%s' error", command)
            error = self._reset_and_create_error(command, message=ex.message)
            raise error from ex

        status = result.invoke_status if result else ""
        _LOGGER.debug("Lock '%s' result: %s", command, status)

        if status.upper() not in ("COMPLETED", "DELIVERED"):
            error = self._reset_and_create_error(
                command, status=status, message=result.message if result else ""
            )
            raise error

        api_field = cast(
            VolvoCarsValue,
            self.coordinator.get_api_field(self.entity_description.api_field),
        )

        if locked:
            self._attr_is_locking = False
            api_field.value = self.entity_description.api_lock_value
        else:
            self._attr_is_unlocking = False
            api_field.value = self.entity_description.api_unlock_value

        self._attr_is_locked = locked
        self.async_write_ha_state()

    def _reset_and_create_error(
        self, command: str, *, status: str = "", message: str = ""
    ) -> HomeAssistantError:
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self.async_write_ha_state()

        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_failure",
            translation_placeholders={
                "command": command,
                "status": status,
                "message": message,
            },
        )
