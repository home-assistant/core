"""Platform for Schlage lock integration."""

from datetime import datetime
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
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> None:
        """Add a lock code."""
        codes = await self._async_fetch_access_codes()
        self._validate_code_name(codes, name)
        self._validate_code_value(codes, code)

        has_start = start_datetime is not None
        has_end = end_datetime is not None

        if has_start != has_end:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schlage_temporary_dates_required",
            )

        schedule = None
        if start_datetime is not None and end_datetime is not None:
            start_utc = dt_util.as_utc(start_datetime)
            end_utc = dt_util.as_utc(end_datetime)
            if start_utc >= end_utc:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="schlage_start_after_end",
                )
            schedule = TemporarySchedule(start=start_utc, end=end_utc)

        access_code = AccessCode(
            name=name,
            code=code,
            notify_on_use=notify_on_use,
            schedule=schedule,
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

    async def delete_code(self, name: str) -> None:
        """Delete a lock code."""
        codes = await self._async_fetch_access_codes()
        if not codes:
            return

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
            # Code not found in defined codes, operation successful
            return

        try:
            await self.hass.async_add_executor_job(codes[code_id_to_delete].delete)
        except SchlageError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="schlage_delete_code_failed",
            ) from ex
        await self.coordinator.async_request_refresh()

    @staticmethod
    def _serialize_recurring(schedule: RecurringSchedule) -> dict[str, Any]:
        """Serialize a single RecurringSchedule to a dict."""
        return {
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

    @staticmethod
    def _serialize_schedule(
        schedule: MultiRecurringSchedule | TemporarySchedule | RecurringSchedule | None,
    ) -> dict[str, Any] | None:
        """Serialize a pyschlage schedule to a dict.

        The returned shape depends on the schedule type.

        ``recurring``: {"type": "recurring", "days_of_week": {"sun": bool, ...},
        "start_hour": int, "start_minute": int, "end_hour": int, "end_minute": int}.
        Times use natural hour and minute values from the pyschlage model.

        ``multi_recurring``: {"type": "multi_recurring", "windows": [<window>, ...]},
        where each window is a dict with the same keys as ``recurring`` (days_of_week,
        start_hour, start_minute, end_hour, end_minute) but without the ``type`` key.
        At most two windows are present.

        ``temporary``: {"type": "temporary", "start_datetime": str, "end_datetime": str}.
        Datetime values are ISO 8601 strings.

        ``None`` returns ``None``.
        """
        if isinstance(schedule, TemporarySchedule):
            return {
                "type": "temporary",
                "start_datetime": schedule.start.isoformat(),
                "end_datetime": schedule.end.isoformat(),
            }
        if isinstance(schedule, MultiRecurringSchedule):
            schedules: list[RecurringSchedule] = []
            if schedule.schedule1 is not None:
                schedules.append(schedule.schedule1)
            if schedule.schedule2 is not None:
                schedules.append(schedule.schedule2)
            windows = [
                SchlageLockEntity._serialize_recurring(sched) for sched in schedules
            ]
            return {"type": "multi_recurring", "windows": windows}
        if isinstance(schedule, RecurringSchedule):
            result = SchlageLockEntity._serialize_recurring(schedule)
            result["type"] = "recurring"
            return result
        return None

    async def get_codes(self) -> ServiceResponse:
        """Get lock codes."""
        await self._async_fetch_access_codes()

        if self._lock.access_codes:
            return {
                code: {
                    "name": self._lock.access_codes[code].name,
                    "code": self._lock.access_codes[code].code,
                    "access_code_id": self._lock.access_codes[code].access_code_id,
                    "schedule": self._serialize_schedule(
                        self._lock.access_codes[code].schedule
                    ),
                }
                for code in self._lock.access_codes
            }
        return {}
