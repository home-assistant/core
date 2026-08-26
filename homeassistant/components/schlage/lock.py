"""Platform for Schlage lock integration."""

from typing import Any, override

from pyschlage.code import (
    AccessCode,
    MultiRecurringSchedule,
    RecurringSchedule,
    TemporarySchedule,
)
from pyschlage.exceptions import Error as SchlageError

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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

    _add_new_locks(coordinator.data)
    coordinator.new_locks_callbacks.append(_add_new_locks)


def _build_schedule(
    start_datetime: Any | None,
    end_datetime: Any | None,
) -> TemporarySchedule | None:
    """Build a schedule object from service parameters.

    Dates alone decide permanence:
      both datetimes present -> TemporarySchedule
      neither present       -> None (permanent code)
      exactly one present   -> error (must provide both or neither)
    """
    if start_datetime is None and end_datetime is None:
        return None
    if start_datetime is None or end_datetime is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="schlage_temporary_dates_required",
        )
    start = dt_util.as_utc(start_datetime)
    end = dt_util.as_utc(end_datetime)
    if start >= end:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="schlage_start_after_end",
        )
    return TemporarySchedule(start=start, end=end)


def _serialize_schedule(
    schedule: Any,
) -> dict[str, Any] | None:
    """Convert a schedule object back to a dict for get_codes() responses."""
    if schedule is None:
        return None

    if isinstance(schedule, TemporarySchedule):
        return {
            "type": "temporary",
            "start_datetime": schedule.start.isoformat(),
            "end_datetime": schedule.end.isoformat(),
        }

    if isinstance(schedule, RecurringSchedule):
        return {
            "type": "recurring",
            "days_of_week": {
                "sun": schedule.days_of_week.sun,
                "mon": schedule.days_of_week.mon,
                "tue": schedule.days_of_week.tue,
                "wed": schedule.days_of_week.wed,
                "thu": schedule.days_of_week.thu,
                "fri": schedule.days_of_week.fri,
                "sat": schedule.days_of_week.sat,
            },
            "start_hour": schedule.start_hour,
            "start_minute": schedule.start_minute,
            "end_hour": schedule.end_hour,
            "end_minute": schedule.end_minute,
        }

    if isinstance(schedule, MultiRecurringSchedule):
        windows: list[dict[str, Any]] = [
            {
                "days_of_week": {
                    "sun": sub.days_of_week.sun,
                    "mon": sub.days_of_week.mon,
                    "tue": sub.days_of_week.tue,
                    "wed": sub.days_of_week.wed,
                    "thu": sub.days_of_week.thu,
                    "fri": sub.days_of_week.fri,
                    "sat": sub.days_of_week.sat,
                },
                "start_hour": sub.start_hour,
                "start_minute": sub.start_minute,
                "end_hour": sub.end_hour,
                "end_minute": sub.end_minute,
            }
            for sub in (schedule.schedule1, schedule.schedule2)
            if sub is not None
        ]
        return {
            "type": "recurring_multi",
            "windows": windows,
        }

    return None


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
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.device_id in self.coordinator.data:
            self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        """Update our internal state attributes."""
        self._attr_is_locked = self._lock.is_locked
        self._attr_is_jammed = self._lock.is_jammed
        self._attr_changed_by = self._lock.last_changed_by()

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self.hass.async_add_executor_job(self._lock.lock)
        await self.coordinator.async_request_refresh()

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self.hass.async_add_executor_job(self._lock.unlock)
        await self.coordinator.async_request_refresh()

    @staticmethod
    def _normalize_code_name(name: str) -> str:
        """Normalize a code name for comparison."""
        return name.lower().strip()

    def _validate_code_name(
        self, codes: dict[str, AccessCode] | None, name: str
    ) -> None:
        """Validate that the code name doesn't already exist."""
        normalized = self._normalize_code_name(name)
        if codes and any(
            self._normalize_code_name(code.name) == normalized
            for code in codes.values()
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_name_exists",
                translation_placeholders={"name": name},
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

    async def _async_fetch_access_codes(self) -> dict[str, AccessCode] | None:
        """Fetch access codes from the lock on demand."""
        try:
            await self.hass.async_add_executor_job(self._lock.refresh_access_codes)
        except SchlageError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schlage_refresh_failed",
            ) from ex
        return self._lock.access_codes

    async def add_code(
        self,
        name: str,
        code: str,
        notify_on_use: bool = True,
        start_datetime: Any | None = None,
        end_datetime: Any | None = None,
    ) -> None:
        """Add a lock code."""
        codes = await self._async_fetch_access_codes()
        self._validate_code_name(codes, name)
        self._validate_code_value(codes, code)

        schedule = _build_schedule(start_datetime, end_datetime)

        access_code = AccessCode(
            name=name, code=code, notify_on_use=notify_on_use, schedule=schedule
        )
        try:
            await self.hass.async_add_executor_job(
                self._lock.add_access_code, access_code
            )
        except SchlageError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schlage_add_code_failed",
            ) from ex
        await self.coordinator.async_request_refresh()

    async def update_code(
        self,
        access_code_id: str,
        name: str | None = None,
        code: str | None = None,
        notify_on_use: bool | None = None,
        disabled: bool | None = None,
        start_datetime: Any | None = None,
        end_datetime: Any | None = None,
    ) -> None:
        """Update a lock code."""
        codes = await self._async_fetch_access_codes()
        if not codes or access_code_id not in codes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_code_not_found",
            )

        target_code = codes[access_code_id]

        # Uniqueness checks against other codes (mirror add_code pattern).
        other_codes = {k: v for k, v in codes.items() if k != access_code_id}
        if name is not None:
            self._validate_code_name(other_codes, name)
        if code is not None:
            self._validate_code_value(other_codes, code)

        if name is not None:
            target_code.name = name
        if code is not None:
            target_code.code = code
        if notify_on_use is not None:
            target_code.notify_on_use = notify_on_use
        if disabled is not None:
            target_code.disabled = disabled

        # Update schedule based on provided datetimes (both or neither).
        has_dates = start_datetime is not None or end_datetime is not None
        if has_dates:
            schedule = _build_schedule(start_datetime, end_datetime)
            target_code.schedule = schedule

        # Capture pre-save schedule for comparison after failed save.
        pre_save_schedule = target_code.schedule

        try:
            await self.hass.async_add_executor_job(target_code.save)
        except SchlageError as ex:
            # The save may have succeeded on the device but the notification
            # to the cloud failed. Verify the update took effect.
            await self._async_fetch_access_codes()
            codes_after = self._lock.access_codes
            if (
                codes_after
                and access_code_id in codes_after
                and codes_after[access_code_id].code == target_code.code
                and codes_after[access_code_id].name == target_code.name
                and codes_after[access_code_id].notify_on_use
                == target_code.notify_on_use
                and codes_after[access_code_id].disabled == target_code.disabled
                and (
                    not has_dates
                    or _serialize_schedule(pre_save_schedule)
                    == _serialize_schedule(codes_after[access_code_id].schedule)
                )
            ):
                await self.coordinator.async_request_refresh()
                return
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schlage_update_code_failed",
            ) from ex
        await self.coordinator.async_request_refresh()

    async def delete_code(
        self, name: str | None = None, access_code_id: str | None = None
    ) -> None:
        """Delete a lock code."""
        if name and access_code_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_delete_code_ambiguous",
            )
        if not access_code_id and not name:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_delete_code_missing_identifier",
            )

        codes = await self._async_fetch_access_codes()
        if not codes:
            return

        code_id_to_delete = None

        if access_code_id:
            if access_code_id in codes:
                code_id_to_delete = access_code_id
            else:
                return
        elif name:
            normalized = self._normalize_code_name(name)
            code_id_to_delete = next(
                (
                    code_id
                    for code_id, code_data in codes.items()
                    if self._normalize_code_name(code_data.name) == normalized
                ),
                None,
            )

        if not code_id_to_delete:
            return

        try:
            await self.hass.async_add_executor_job(codes[code_id_to_delete].delete)
        except SchlageError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schlage_delete_code_failed",
            ) from ex
        await self.coordinator.async_request_refresh()

    async def get_codes(self) -> ServiceResponse:
        """Get lock codes."""
        await self._async_fetch_access_codes()

        if self._lock.access_codes:
            return {
                code_id: {
                    "name": self._lock.access_codes[code_id].name,
                    "code": self._lock.access_codes[code_id].code,
                    "access_code_id": self._lock.access_codes[code_id].access_code_id,
                    "disabled": self._lock.access_codes[code_id].disabled,
                    "notify_on_use": self._lock.access_codes[code_id].notify_on_use,
                    "schedule": _serialize_schedule(
                        self._lock.access_codes[code_id].schedule
                    ),
                }
                for code_id in self._lock.access_codes
            }
        return {}
