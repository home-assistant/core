"""Keep ZHA thermostat weekly schedules in sync with schedule helpers.

The helper is the source of truth. Conversion and syncing only rely on the
generic `weekly_schedule` provider of ZHA thermostat entities, so any thermostat
family whose quirk exposes a schedule provider can be linked.
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import logging
from typing import TYPE_CHECKING, Any, Literal
import uuid

from zha.exceptions import ZHAException

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.components.schedule.const import (
    CONF_DATA,
    CONF_FROM,
    CONF_TO,
    DOMAIN as SCHEDULE_DOMAIN,
    WEEKDAY_TO_CONF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    EventStateReportedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_state_report_event,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from zha.zigbee.weekly_schedule import WeeklyScheduleProvider

    from .helpers import ZHAGatewayProxy

_LOGGER = logging.getLogger(__name__)

CONF_WEEKLY_SCHEDULE_LINKS = "weekly_schedule_links"
ATTR_TEMPERATURE = "temperature"
SIGNAL_WEEKLY_SCHEDULE_UPDATED = "zha_weekly_schedule_updated"

SYNC_COOLDOWN = 5
RETRY_DELAY = timedelta(minutes=15)

ISSUE_SYNC_FAILED = "weekly_schedule_sync_failed"
ISSUE_LINK_BROKEN = "weekly_schedule_link_broken"

WEEKDAYS = tuple(WEEKDAY_TO_CONF.values())

type SyncState = Literal["pending", "syncing", "synced", "error"]
type Transitions = dict[str, list[tuple[int, int]]]


class ScheduleConversionError(ValueError):
    """A schedule helper cannot be represented as heat transitions."""


class WeeklyScheduleRemovalError(HomeAssistantError):
    """The device schedule could not be safely cleared before unlinking."""


def _centi_celsius(value: Any, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScheduleConversionError(
            f"{description} must be a number in °C. For a time block, enter "
            "`temperature: 23` in Additional data, or set a default time block temperature "
            "when linking the helper."
        )
    try:
        centi_celsius = Decimal(str(value)) * 100
    except InvalidOperation as exc:
        raise ScheduleConversionError(
            f"{description} must be a finite temperature in °C."
        ) from exc
    if not centi_celsius.is_finite():
        raise ScheduleConversionError(
            f"{description} must be a finite temperature in °C."
        )
    if centi_celsius != centi_celsius.to_integral_value():
        raise ScheduleConversionError(f"{description} must use increments of 0.01 °C.")
    if not -32767 <= centi_celsius <= 32767:
        raise ScheduleConversionError(
            f"{description} ({value} °C) is outside the supported range "
            "of -327.67 to 327.67 °C."
        )
    return int(centi_celsius)


def _minute(value: Any, day: str, *, end: bool) -> int:
    if not isinstance(value, time):
        raise ScheduleConversionError(f"Invalid schedule times for {day}")
    if end and value == time.max:
        return 1440
    if value.tzinfo is not None or value.second or value.microsecond:
        raise ScheduleConversionError(
            f"Schedule times for {day} must use exact local minutes"
        )
    return value.hour * 60 + value.minute


def schedule_to_transitions(
    schedule: Any,
    *,
    block_temperature: float | None = None,
    gap_temperature: float | None = None,
) -> Transitions:
    """Convert a schedule helper configuration into heat transitions.

    A time block uses its `data.temperature`, else `block_temperature`. Time not
    covered by a time block uses `gap_temperature`. Without these fallbacks,
    every time block needs a temperature and every day must be fully covered.
    """
    if not isinstance(schedule, Mapping) or set(schedule) != set(WEEKDAYS):
        raise ScheduleConversionError("The schedule helper must contain seven weekdays")

    result: Transitions = {}
    for day in WEEKDAYS:
        blocks = schedule[day]
        if not isinstance(blocks, list) or not all(
            isinstance(block, Mapping) for block in blocks
        ):
            raise ScheduleConversionError(f"Invalid time block for {day}")
        coverage_error = (
            f"The {day.capitalize()} schedule has times without a temperature. "
            "Set a default temperature outside of time blocks when linking "
            "the helper, or add time blocks covering the whole day "
            "from 00:00 to 24:00."
        )
        gap = (
            _centi_celsius(
                gap_temperature,
                f"The default temperature outside of {day.capitalize()}'s time blocks",
            )
            if gap_temperature is not None
            else None
        )
        if not blocks and gap is None:
            raise ScheduleConversionError(coverage_error)

        transitions: list[tuple[int, int]] = []
        cursor = 0
        for block_number, block in enumerate(
            sorted(
                blocks,
                key=lambda block: (
                    block.get(CONF_FROM)
                    if isinstance(block.get(CONF_FROM), time)
                    else time.min
                ),
            ),
            start=1,
        ):
            start = _minute(block.get(CONF_FROM), day, end=False)
            stop = _minute(block.get(CONF_TO), day, end=True)
            if start < cursor or stop <= start:
                raise ScheduleConversionError(
                    f"The {day.capitalize()} schedule has overlapping time blocks "
                    "or a time block whose end is not after its start. Adjust "
                    "the time blocks so each ends after it starts and none overlap."
                )
            if start > cursor:
                if gap is None:
                    raise ScheduleConversionError(coverage_error)
                transitions.append((cursor, gap))
            data = block.get(CONF_DATA)
            if data is not None and not isinstance(data, Mapping):
                raise ScheduleConversionError(
                    f"The Additional data for {day.capitalize()}'s time block {block_number} must "
                    "be a YAML mapping. Enter `temperature: 23` (with a colon), "
                    "not `temperature=23`."
                )
            temperature = data.get(ATTR_TEMPERATURE) if data is not None else None
            if temperature is None:
                temperature = block_temperature
            if temperature is None:
                raise ScheduleConversionError(
                    f"{day.capitalize()}'s time block {block_number} has no temperature. Add "
                    "`temperature: 23` under Additional data, or set a default time block "
                    "temperature when linking the helper."
                )
            transitions.append(
                (
                    start,
                    _centi_celsius(
                        temperature,
                        f"The temperature for {day.capitalize()}'s time block {block_number}",
                    ),
                )
            )
            cursor = stop
        if cursor < 1440:
            if gap is None:
                raise ScheduleConversionError(coverage_error)
            transitions.append((cursor, gap))

        merged: list[tuple[int, int]] = []
        for minute, temperature in transitions:
            if not merged or merged[-1][1] != temperature:
                merged.append((minute, temperature))
        result[day] = merged
    return result


@dataclass(frozen=True, kw_only=True)
class WeeklyScheduleLink:
    """A thermostat kept in sync with a schedule helper.

    Entities are stored by entity registry ID so renames keep the link.
    """

    link_id: str
    thermostat: str
    schedule: str
    block_temperature: float | None = None
    gap_temperature: float | None = None

    @classmethod
    def from_options(cls, data: Mapping[str, Any]) -> WeeklyScheduleLink:
        """Create a link from stored options."""
        return cls(
            link_id=data["link_id"],
            thermostat=data["thermostat"],
            schedule=data["schedule"],
            block_temperature=data.get("block_temperature"),
            gap_temperature=data.get("gap_temperature"),
        )

    def as_options(self) -> dict[str, Any]:
        """Return the stored representation."""
        return {
            "link_id": self.link_id,
            "thermostat": self.thermostat,
            "schedule": self.schedule,
            "block_temperature": self.block_temperature,
            "gap_temperature": self.gap_temperature,
        }


def _thermostat_provider(
    gateway_proxy: ZHAGatewayProxy, entity_id: str
) -> WeeklyScheduleProvider | None:
    """Return the schedule provider of a ZHA climate entity, if any."""
    for references in gateway_proxy.ha_entity_refs.values():
        for reference in references:
            if reference.ha_entity_id == entity_id:
                return getattr(reference.entity_data.entity, "weekly_schedule", None)
    return None


class _LinkSync:
    """Sync state and listeners for one link."""

    def __init__(
        self, manager: WeeklyScheduleSyncManager, link: WeeklyScheduleLink
    ) -> None:
        """Initialize the link sync."""
        self.manager = manager
        self.hass = manager.hass
        self.link = link
        self.state: SyncState = "pending"
        # Set while the link is being removed so no sync writes the schedule back.
        self._paused = False
        self._stopped = False
        self._sync_lock = asyncio.Lock()
        self._sync_generation = 0
        self.last_synced_at: datetime | None = None
        self.last_error: str | None = None
        self.last_sync_succeeded = False
        self.written_days: list[str] = []
        self._synced_transitions: Transitions | None = None
        self._started = False
        self._tracked_entity_id: str | None = None
        self._unsub_started: CALLBACK_TYPE | None = None
        self._unsub_helper: list[CALLBACK_TYPE] = []
        self._unsub_retry: CALLBACK_TYPE | None = None
        self._debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=SYNC_COOLDOWN,
            immediate=False,
            function=self._async_sync,
            background=True,
        )

    @callback
    def async_start(self) -> None:
        """Track the helper and sync once Home Assistant has started."""
        self.async_track_helper()
        self._unsub_started = async_at_started(self.hass, self._async_started)

    async def _async_started(self, _hass: HomeAssistant) -> None:
        self._unsub_started = None
        self._started = True
        self.async_request_sync()

    @callback
    def async_track_helper(self) -> None:
        """(Re)subscribe when the helper's entity ID changes."""
        entity_id = er.async_resolve_entity_id(
            er.async_get(self.hass), self.link.schedule
        )
        if entity_id == self._tracked_entity_id:
            return
        self._untrack_helper()
        self._tracked_entity_id = entity_id
        if entity_id is None:
            # Surface the broken link instead of silently stopping.
            self.async_request_sync()
            return
        self._unsub_helper = [
            async_track_state_change_event(
                self.hass, entity_id, self._async_helper_updated
            ),
            # Editing blocks may not change the helper's state or attributes.
            async_track_state_report_event(
                self.hass, entity_id, self._async_helper_updated
            ),
        ]
        self.async_request_sync()

    @callback
    def _untrack_helper(self) -> None:
        for unsub in self._unsub_helper:
            unsub()
        self._unsub_helper = []

    @callback
    def _async_helper_updated(
        self, _event: Event[EventStateChangedData] | Event[EventStateReportedData]
    ) -> None:
        self.async_request_sync()

    @callback
    def async_request_sync(self, *, force: bool = False) -> None:
        """Schedule a debounced sync once Home Assistant has started."""
        self._sync_generation += 1
        if force:
            self._synced_transitions = None
        if self._started and not self._paused and not self._stopped:
            self._debouncer.async_schedule_call()

    @callback
    def async_provider_invalidated(self) -> None:
        """Resync when an external operation changes a previously synced schedule."""
        if self.state != "synced" or self._paused or self._stopped:
            return
        self.state = "pending"
        self.last_sync_succeeded = False
        self.async_request_sync(force=True)
        self.manager.async_notify()

    @callback
    def async_pause(self, paused: bool = True) -> None:
        """Stop or resume automatic syncs."""
        if self._stopped:
            return
        self._paused = paused
        if not paused:
            self.async_request_sync(force=True)
            return
        self._cancel_retry()
        self._debouncer.async_cancel()
        self.last_sync_succeeded = False
        self.manager.async_notify()

    async def async_wait_idle(self) -> None:
        """Wait for an already running sync to finish."""
        async with self._sync_lock:
            pass

    async def async_sync_now(self) -> None:
        """Sync immediately."""
        self._synced_transitions = None
        self._sync_generation += 1
        self._debouncer.async_cancel()
        await self._async_sync()

    @callback
    def async_stop(self, *, remove_issues: bool) -> None:
        """Stop tracking and cancel pending syncs."""
        self._stopped = True
        self._paused = True
        if self._unsub_started is not None:
            self._unsub_started()
            self._unsub_started = None
        self._untrack_helper()
        self._tracked_entity_id = None
        self._started = False
        self._cancel_retry()
        self._debouncer.async_shutdown()
        if remove_issues:
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id(ISSUE_SYNC_FAILED))
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id(ISSUE_LINK_BROKEN))

    def issue_id(self, kind: str) -> str:
        """Return the repair issue ID for this link."""
        return f"{kind}_{self.link.link_id}"

    @callback
    def _cancel_retry(self) -> None:
        if self._unsub_retry is not None:
            self._unsub_retry()
            self._unsub_retry = None

    @callback
    def _async_retry(self, _now: datetime) -> None:
        self._unsub_retry = None
        self.async_request_sync()

    def as_dict(self) -> dict[str, Any]:
        """Return the link and its sync status."""
        registry = er.async_get(self.hass)
        return {
            "link_id": self.link.link_id,
            "thermostat_entity_id": er.async_resolve_entity_id(
                registry, self.link.thermostat
            ),
            "schedule_entity_id": er.async_resolve_entity_id(
                registry, self.link.schedule
            ),
            "block_temperature": self.link.block_temperature,
            "gap_temperature": self.link.gap_temperature,
            "state": self.state,
            "last_synced_at": (
                self.last_synced_at.isoformat() if self.last_synced_at else None
            ),
            "last_error": self.last_error,
            "written_days": self.written_days,
        }

    def _fail(self, kind: str, error: str, *, retry: bool) -> None:
        self.state = "error"
        self.last_sync_succeeded = False
        self.last_error = error
        other = ISSUE_LINK_BROKEN if kind == ISSUE_SYNC_FAILED else ISSUE_SYNC_FAILED
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id(other))
        registry = er.async_get(self.hass)
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self.issue_id(kind),
            is_fixable=True,
            is_persistent=False,
            data={"link_id": self.link.link_id},
            severity=ir.IssueSeverity.ERROR,
            translation_key=kind,
            translation_placeholders={
                "thermostat": er.async_resolve_entity_id(registry, self.link.thermostat)
                or self.link.thermostat,
                "schedule": er.async_resolve_entity_id(registry, self.link.schedule)
                or self.link.schedule,
                "error": error,
            },
        )
        if retry:
            self._cancel_retry()
            self._unsub_retry = async_call_later(
                self.hass, RETRY_DELAY, self._async_retry
            )
        self.manager.async_notify()

    def _sync_is_current(self, generation: int) -> bool:
        return (
            not self._paused
            and not self._stopped
            and generation == self._sync_generation
        )

    async def _async_sync(self) -> None:
        """Serialize syncs and preserve changes made during a slow upload."""
        async with self._sync_lock:
            if self._paused or self._stopped:
                return
            generation = self._sync_generation
            try:
                await self._async_sync_once(generation)
            finally:
                if (
                    generation != self._sync_generation
                    and self._started
                    and not self._paused
                    and not self._stopped
                ):
                    self.state = "pending"
                    self.last_sync_succeeded = False
                    self.manager.async_notify()
                    self._debouncer.async_schedule_call()

    async def _async_sync_once(self, generation: int) -> None:
        """Convert the helper and write the days that differ."""
        self._cancel_retry()
        registry = er.async_get(self.hass)
        thermostat_id = er.async_resolve_entity_id(registry, self.link.thermostat)
        schedule_id = er.async_resolve_entity_id(registry, self.link.schedule)
        if thermostat_id is None or schedule_id is None:
            self._fail(
                ISSUE_LINK_BROKEN,
                "The thermostat or schedule helper no longer exists",
                retry=False,
            )
            return
        provider = _thermostat_provider(self.manager.gateway_proxy, thermostat_id)
        if provider is None:
            self._fail(
                ISSUE_SYNC_FAILED,
                "The thermostat is not loaded or does not support weekly schedules",
                retry=True,
            )
            return

        try:
            response = await self.hass.services.async_call(
                SCHEDULE_DOMAIN,
                "get_schedule",
                {"entity_id": schedule_id},
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as exc:
            if self._sync_is_current(generation):
                self._fail(ISSUE_LINK_BROKEN, str(exc), retry=False)
            return
        if not self._sync_is_current(generation):
            return
        try:
            transitions = schedule_to_transitions(
                (response or {}).get(schedule_id),
                block_temperature=self.link.block_temperature,
                gap_temperature=self.link.gap_temperature,
            )
        except ScheduleConversionError as exc:
            self._fail(ISSUE_SYNC_FAILED, str(exc), retry=False)
            return

        if transitions == self._synced_transitions and self.state == "synced":
            return
        self.state = "syncing"
        self.manager.async_notify()
        try:
            result = await provider.async_set(transitions, only_changed=True)
        except ZHAException as exc:
            if not self._sync_is_current(generation):
                return
            _LOGGER.warning(
                "Weekly schedule sync from %s to %s failed: %s",
                schedule_id,
                thermostat_id,
                exc,
            )
            self._synced_transitions = None
            self._fail(ISSUE_SYNC_FAILED, str(exc), retry=True)
            return

        if not self._sync_is_current(generation):
            return
        self._synced_transitions = transitions
        self.state = "synced"
        self.last_sync_succeeded = True
        self.last_error = None
        self.last_synced_at = dt_util.utcnow()
        self.written_days = list(result["written_days"])
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id(ISSUE_SYNC_FAILED))
        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id(ISSUE_LINK_BROKEN))
        self.manager.async_notify()


class WeeklyScheduleSyncManager:
    """Manage the thermostat to schedule helper links stored in ZHA options."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        gateway_proxy: ZHAGatewayProxy,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.config_entry = config_entry
        self.gateway_proxy = gateway_proxy
        self._links: dict[str, _LinkSync] = {}
        self._changing_links: set[str] = set()
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_registry: CALLBACK_TYPE | None = None

    @callback
    def async_start(self) -> None:
        """Start syncing all stored links."""
        for data in self.config_entry.options.get(CONF_WEEKLY_SCHEDULE_LINKS, []):
            link = WeeklyScheduleLink.from_options(data)
            self._start_link(link)
        self._unsub_registry = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._async_registry_updated,
            event_filter=self._registry_event_filter,
        )

    @callback
    def async_shutdown(self) -> None:
        """Stop all syncing without removing repairs of stored links."""
        if self._unsub_registry is not None:
            self._unsub_registry()
            self._unsub_registry = None
        for link_sync in self._links.values():
            link_sync.async_stop(remove_issues=False)
        self._links.clear()

    @callback
    def _registry_event_filter(self, data: er.EventEntityRegistryUpdatedData) -> bool:
        return data["entity_id"].split(".", 1)[0] in (SCHEDULE_DOMAIN, CLIMATE_DOMAIN)

    @callback
    def _async_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        for link_sync in self._links.values():
            link_sync.async_track_helper()
            if event.data["action"] == "remove":
                link_sync.async_request_sync()

    @callback
    def async_subscribe(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Call `listener` whenever a link's status changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_notify(self) -> None:
        """Notify status listeners."""
        for listener in list(self._listeners):
            listener()
        async_dispatcher_send(self.hass, SIGNAL_WEEKLY_SCHEDULE_UPDATED)

    @callback
    def async_schedule_active(self, thermostat_entity_id: str) -> bool:
        """Return whether an uploaded schedule can safely be offered as Auto."""
        registry = er.async_get(self.hass)
        if (entry := registry.async_get(thermostat_entity_id)) is None:
            return False
        link_sync = next(
            (
                link_sync
                for link_sync in self._links.values()
                if link_sync.link.thermostat == entry.id
            ),
            None,
        )
        if link_sync is not None and not link_sync.last_sync_succeeded:
            return False
        provider = _thermostat_provider(self.gateway_proxy, thermostat_entity_id)
        return provider is not None and bool(
            getattr(provider, "has_verified_schedule", False)
        )

    @callback
    def async_schedule_invalidated(self, thermostat_entity_id: str) -> None:
        """Resync a linked thermostat whose verified schedule became unknown."""
        registry = er.async_get(self.hass)
        if (entry := registry.async_get(thermostat_entity_id)) is None:
            return
        for link_sync in self._links.values():
            if link_sync.link.thermostat == entry.id:
                link_sync.async_provider_invalidated()
                return

    @callback
    def _start_link(self, link: WeeklyScheduleLink) -> _LinkSync:
        link_sync = _LinkSync(self, link)
        self._links[link.link_id] = link_sync
        link_sync.async_start()
        return link_sync

    @callback
    def _persist(self) -> None:
        options = dict(self.config_entry.options)
        if self._links:
            options[CONF_WEEKLY_SCHEDULE_LINKS] = [
                link_sync.link.as_options() for link_sync in self._links.values()
            ]
        else:
            options.pop(CONF_WEEKLY_SCHEDULE_LINKS, None)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=options,
        )

    @callback
    def async_supported_thermostats(self) -> list[dict[str, Any]]:
        """Return ZHA climate entities that expose a weekly schedule provider."""
        result = []
        for references in self.gateway_proxy.ha_entity_refs.values():
            for reference in references:
                if not reference.ha_entity_id.startswith(f"{CLIMATE_DOMAIN}."):
                    continue
                provider = getattr(
                    reference.entity_data.entity, "weekly_schedule", None
                )
                if provider is None or not provider.capabilities.supports_clear:
                    continue
                result.append(
                    {
                        "entity_id": reference.ha_entity_id,
                        "device_id": reference.entity_data.device_proxy.device_id,
                        "capabilities": provider.capabilities.as_dict(),
                    }
                )
        return sorted(result, key=lambda item: item["entity_id"])

    @callback
    def async_links(self) -> list[dict[str, Any]]:
        """Return all links with their status."""
        return [link_sync.as_dict() for link_sync in self._links.values()]

    @callback
    def async_add_link(
        self,
        thermostat_entity_id: str,
        schedule_entity_id: str,
        *,
        block_temperature: float | None = None,
        gap_temperature: float | None = None,
    ) -> dict[str, Any]:
        """Link a supported thermostat to a schedule helper and start syncing."""
        registry = er.async_get(self.hass)
        thermostat = registry.async_get(thermostat_entity_id)
        schedule = registry.async_get(schedule_entity_id)
        if thermostat is None or thermostat.platform != DOMAIN:
            raise ValueError(f"{thermostat_entity_id} is not a ZHA thermostat")
        provider = _thermostat_provider(self.gateway_proxy, thermostat_entity_id)
        if provider is None:
            raise ValueError(
                f"{thermostat_entity_id} does not support weekly schedules"
            )
        if not provider.capabilities.supports_clear:
            raise ValueError(
                f"{thermostat_entity_id} cannot clear weekly schedules and cannot "
                "be linked safely"
            )
        if schedule is None or schedule.domain != SCHEDULE_DOMAIN:
            raise ValueError(f"{schedule_entity_id} is not a schedule helper")
        if any(
            link_sync.link.thermostat == thermostat.id
            for link_sync in self._links.values()
        ):
            raise ValueError(f"{thermostat_entity_id} is already linked")
        link = WeeklyScheduleLink(
            link_id=uuid.uuid4().hex,
            thermostat=thermostat.id,
            schedule=schedule.id,
            block_temperature=block_temperature,
            gap_temperature=gap_temperature,
        )
        link_sync = self._start_link(link)
        self._persist()
        self.async_notify()
        return link_sync.as_dict()

    def _check_link_not_changing(self, link_id: str) -> None:
        if link_id in self._changing_links:
            raise HomeAssistantError(
                "The weekly schedule link is already being changed"
            )

    async def async_update_link(
        self,
        link_id: str,
        schedule_entity_id: str,
        *,
        block_temperature: float | None = None,
        gap_temperature: float | None = None,
    ) -> dict[str, Any]:
        """Change the helper or fallback temperatures of a link and resync."""
        self._check_link_not_changing(link_id)
        old_sync = self._links[link_id]
        schedule = er.async_get(self.hass).async_get(schedule_entity_id)
        if schedule is None or schedule.domain != SCHEDULE_DOMAIN:
            raise ValueError(f"{schedule_entity_id} is not a schedule helper")
        link = WeeklyScheduleLink(
            link_id=link_id,
            thermostat=old_sync.link.thermostat,
            schedule=schedule.id,
            block_temperature=block_temperature,
            gap_temperature=gap_temperature,
        )
        self._changing_links.add(link_id)
        old_sync.async_pause()
        try:
            await old_sync.async_wait_idle()
            old_sync.async_stop(remove_issues=True)
            link_sync = self._start_link(link)
            self._persist()
            self.async_notify()
            return link_sync.as_dict()
        finally:
            self._changing_links.discard(link_id)
            if self._links.get(link_id) is old_sync:
                old_sync.async_pause(False)

    async def async_remove_link(
        self, link_id: str, *, without_clearing: bool = False
    ) -> None:
        """Leave Auto, clear the device schedule, and forget the link."""
        self._check_link_not_changing(link_id)
        link_sync = self._links[link_id]
        if not without_clearing:
            self._clear_target(link_sync)
        self._changing_links.add(link_id)
        link_sync.async_pause()
        try:
            await link_sync.async_wait_idle()
            if not without_clearing:
                await self._async_clear_device(link_sync)
            self._links.pop(link_id)
            link_sync.async_stop(remove_issues=True)
            self._persist()
            self.async_notify()
        finally:
            self._changing_links.discard(link_id)
            if self._links.get(link_id) is link_sync:
                link_sync.async_pause(False)

    def _clear_target(
        self, link_sync: _LinkSync
    ) -> tuple[str, WeeklyScheduleProvider, HVACMode]:
        thermostat_id = er.async_resolve_entity_id(
            er.async_get(self.hass), link_sync.link.thermostat
        )
        provider = (
            _thermostat_provider(self.gateway_proxy, thermostat_id)
            if thermostat_id
            else None
        )
        if provider is None or thermostat_id is None:
            raise WeeklyScheduleRemovalError(
                "The thermostat is not available, so its schedule was not cleared"
            )
        if not provider.capabilities.supports_clear:
            raise WeeklyScheduleRemovalError(
                f"{thermostat_id} does not support clearing weekly schedules"
            )
        state = self.hass.states.get(thermostat_id)
        try:
            mode = HVACMode(state.state) if state is not None else None
        except ValueError:
            mode = None
        if mode is None:
            raise WeeklyScheduleRemovalError(
                f"The current mode of {thermostat_id} is unknown or unavailable, "
                "so its schedule was not cleared"
            )
        return thermostat_id, provider, mode

    async def _async_clear_device(self, link_sync: _LinkSync) -> None:
        thermostat_id, provider, mode = self._clear_target(link_sync)
        try:
            if mode in (HVACMode.AUTO, HVACMode.HEAT_COOL):
                await self.hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_SET_HVAC_MODE,
                    {ATTR_ENTITY_ID: thermostat_id, ATTR_HVAC_MODE: HVACMode.HEAT},
                    blocking=True,
                )
            await provider.async_clear()
        except (HomeAssistantError, ZHAException) as exc:
            raise WeeklyScheduleRemovalError(
                f"Could not clear the weekly schedule of {thermostat_id}: {exc}"
            ) from exc

    @callback
    def async_request_sync(self, link_id: str) -> None:
        """Re-read the device and write differing days."""
        self._check_link_not_changing(link_id)
        self._links[link_id].async_request_sync(force=True)

    async def async_sync_now(self, link_id: str) -> None:
        """Sync a link, waiting for the result."""
        self._check_link_not_changing(link_id)
        await self._links[link_id].async_sync_now()
