"""Support for Google Calendar Search binary sensors."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import itertools
import logging
from typing import Any, cast

from gcal_sync.api import (
    GoogleCalendarService,
    ListEventsRequest,
    Range,
    SyncEventsRequest,
)
from gcal_sync.exceptions import ApiException
from gcal_sync.model import AccessRole, DateOrDatetime, Event
from gcal_sync.store import ScopedCalendarStore
from gcal_sync.sync import CalendarEventSyncManager
from gcal_sync.timeline import Timeline
from ical.iter import SortableItemValue

from homeassistant.components.calendar import (
    CREATE_EVENT_SCHEMA,
    ENTITY_ID_FORMAT,
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_LOCATION,
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
    extract_offset,
    is_offset_reached,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_ENTITIES, CONF_NAME, CONF_OFFSET
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import entity_platform, entity_registry as er
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from . import (
    CONF_IGNORE_AVAILABILITY,
    CONF_SEARCH,
    CONF_TRACK,
    DEFAULT_CONF_OFFSET,
    DOMAIN,
    YAML_DEVICES,
    get_calendar_info,
    load_config,
    update_config,
)
from .api import get_feature_access
from .const import (
    DATA_SERVICE,
    DATA_STORE,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
    FeatureAccess,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)
# Maximum number of upcoming events to consider for state changes between
# coordinator updates.
MAX_UPCOMING_EVENTS = 20

# Avoid syncing super old data on initial syncs. Note that old but active
# recurring events are still included.
SYNC_EVENT_MIN_TIME = timedelta(days=-90)

# Events have a transparency that determine whether or not they block time on calendar.
# When an event is opaque, it means "Show me as busy" which is the default.  Events that
# are not opaque are ignored by default.
OPAQUE = "opaque"

# Google calendar prefixes recurrence rules with RRULE: which
# we need to strip when working with the frontend recurrence rule values
RRULE_PREFIX = "RRULE:"

SERVICE_CREATE_EVENT = "create_event"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the google calendar platform."""
    calendar_service = hass.data[DOMAIN][config_entry.entry_id][DATA_SERVICE]
    store = hass.data[DOMAIN][config_entry.entry_id][DATA_STORE]
    try:
        result = await calendar_service.async_list_calendars()
    except ApiException as err:
        raise PlatformNotReady(str(err)) from err

    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    entity_entry_map = {
        entity_entry.unique_id: entity_entry for entity_entry in registry_entries
    }

    # Yaml configuration may override objects from the API
    calendars = await hass.async_add_executor_job(
        load_config, hass.config.path(YAML_DEVICES)
    )
    new_calendars = []
    entities = []
    for calendar_item in result.items:
        calendar_id = calendar_item.id
        if calendars and calendar_id in calendars:
            calendar_info = calendars[calendar_id]
        else:
            calendar_info = get_calendar_info(
                hass, calendar_item.dict(exclude_unset=True)
            )
            new_calendars.append(calendar_info)
        # Yaml calendar config may map one calendar to multiple entities
        # with extra options like offsets or search criteria.
        num_entities = len(calendar_info[CONF_ENTITIES])
        for data in calendar_info[CONF_ENTITIES]:
            entity_enabled = data.get(CONF_TRACK, True)
            if not entity_enabled:
                _LOGGER.warning(
                    "The 'track' option in google_calendars.yaml has been deprecated."
                    " The setting has been imported to the UI, and should now be"
                    " removed from google_calendars.yaml"
                )
            entity_name = data[CONF_DEVICE_ID]
            # The unique id is based on the config entry and calendar id since
            # multiple accounts can have a common calendar id
            # (e.g. `en.usa#holiday@group.v.calendar.google.com`).
            # When using google_calendars.yaml with multiple entities for a
            # single calendar, we have no way to set a unique id.
            if num_entities > 1:
                unique_id = None
            else:
                unique_id = f"{config_entry.unique_id}-{calendar_id}"
            # Migrate to new unique_id format which supports
            # multiple config entries as of 2022.7
            for old_unique_id in (calendar_id, f"{calendar_id}-{entity_name}"):
                if not (entity_entry := entity_entry_map.get(old_unique_id)):
                    continue
                if unique_id:
                    _LOGGER.debug(
                        "Migrating unique_id for %s from %s to %s",
                        entity_entry.entity_id,
                        old_unique_id,
                        unique_id,
                    )
                    entity_registry.async_update_entity(
                        entity_entry.entity_id, new_unique_id=unique_id
                    )
                else:
                    _LOGGER.debug(
                        "Removing entity registry entry for %s from %s",
                        entity_entry.entity_id,
                        old_unique_id,
                    )
                    entity_registry.async_remove(
                        entity_entry.entity_id,
                    )
            coordinator: CalendarSyncUpdateCoordinator | CalendarQueryUpdateCoordinator
            # Prefer calendar sync down of resources when possible. However,
            # sync does not work for search. Also free-busy calendars denormalize
            # recurring events as individual events which is not efficient for sync
            support_write = (
                calendar_item.access_role.is_writer
                and get_feature_access(hass, config_entry) is FeatureAccess.read_write
            )
            if (
                search := data.get(CONF_SEARCH)
            ) or calendar_item.access_role == AccessRole.FREE_BUSY_READER:
                coordinator = CalendarQueryUpdateCoordinator(
                    hass,
                    calendar_service,
                    data[CONF_NAME],
                    calendar_id,
                    search,
                )
                support_write = False
            else:
                request_template = SyncEventsRequest(
                    calendar_id=calendar_id,
                    start_time=dt_util.now() + SYNC_EVENT_MIN_TIME,
                )
                sync = CalendarEventSyncManager(
                    calendar_service,
                    store=ScopedCalendarStore(store, unique_id or entity_name),
                    request_template=request_template,
                )
                coordinator = CalendarSyncUpdateCoordinator(
                    hass,
                    sync,
                    data[CONF_NAME],
                )
            entities.append(
                GoogleCalendarEntity(
                    coordinator,
                    calendar_id,
                    data,
                    generate_entity_id(ENTITY_ID_FORMAT, entity_name, hass=hass),
                    unique_id,
                    entity_enabled,
                    support_write,
                )
            )

    async_add_entities(entities)

    if calendars and new_calendars:

        def append_calendars_to_config() -> None:
            path = hass.config.path(YAML_DEVICES)
            for calendar in new_calendars:
                update_config(path, calendar)

        await hass.async_add_executor_job(append_calendars_to_config)

    platform = entity_platform.async_get_current_platform()
    if (
        any(calendar_item.access_role.is_writer for calendar_item in result.items)
        and get_feature_access(hass, config_entry) is FeatureAccess.read_write
    ):
        platform.async_register_entity_service(
            SERVICE_CREATE_EVENT,
            CREATE_EVENT_SCHEMA,
            async_create_event,
            required_features=CalendarEntityFeature.CREATE_EVENT,
        )


def _truncate_timeline(timeline: Timeline, max_events: int) -> Timeline:
    """Truncate the timeline to a maximum number of events.

    This is used to avoid repeated expansion of recurring events during
    state machine updates.
    """
    upcoming = timeline.active_after(dt_util.now())
    truncated = list(itertools.islice(upcoming, max_events))
    return Timeline(
        [
            SortableItemValue(event.timespan_of(dt_util.DEFAULT_TIME_ZONE), event)
            for event in truncated
        ]
    )


class CalendarSyncUpdateCoordinator(DataUpdateCoordinator[Timeline]):  # pylint: disable=hass-enforce-coordinator-module
    """Coordinator for calendar RPC calls that use an efficient sync."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        sync: CalendarEventSyncManager,
        name: str,
    ) -> None:
        """Create the CalendarSyncUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.sync = sync
        self._upcoming_timeline: Timeline | None = None

    async def _async_update_data(self) -> Timeline:
        """Fetch data from API endpoint."""
        try:
            await self.sync.run()
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        timeline = await self.sync.store_service.async_get_timeline(
            dt_util.DEFAULT_TIME_ZONE
        )
        self._upcoming_timeline = _truncate_timeline(timeline, MAX_UPCOMING_EVENTS)
        return timeline

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> Iterable[Event]:
        """Get all events in a specific time frame."""
        if not self.data:
            raise HomeAssistantError(
                "Unable to get events: Sync from server has not completed"
            )
        return self.data.overlapping(
            start_date,
            end_date,
        )

    @property
    def upcoming(self) -> Iterable[Event] | None:
        """Return upcoming events if any."""
        if self._upcoming_timeline:
            return self._upcoming_timeline.active_after(dt_util.now())
        return None


class CalendarQueryUpdateCoordinator(DataUpdateCoordinator[list[Event]]):  # pylint: disable=hass-enforce-coordinator-module
    """Coordinator for calendar RPC calls.

    This sends a polling RPC, not using sync, as a workaround
    for limitations in the calendar API for supporting search.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        calendar_service: GoogleCalendarService,
        name: str,
        calendar_id: str,
        search: str | None,
    ) -> None:
        """Create the CalendarQueryUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self._search = search

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> Iterable[Event]:
        """Get all events in a specific time frame."""
        request = ListEventsRequest(
            calendar_id=self.calendar_id,
            start_time=start_date,
            end_time=end_date,
            search=self._search,
        )
        result_items = []
        try:
            result = await self.calendar_service.async_list_events(request)
            async for result_page in result:
                result_items.extend(result_page.items)
        except ApiException as err:
            self.async_set_update_error(err)
            raise HomeAssistantError(str(err)) from err
        return result_items

    async def _async_update_data(self) -> list[Event]:
        """Fetch data from API endpoint."""
        request = ListEventsRequest(calendar_id=self.calendar_id, search=self._search)
        try:
            result = await self.calendar_service.async_list_events(request)
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return result.items

    @property
    def upcoming(self) -> Iterable[Event] | None:
        """Return the next upcoming event if any."""
        return self.data


class GoogleCalendarEntity(
    CoordinatorEntity[CalendarSyncUpdateCoordinator | CalendarQueryUpdateCoordinator],
    CalendarEntity,
):
    """A calendar event entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CalendarSyncUpdateCoordinator | CalendarQueryUpdateCoordinator,
        calendar_id: str,
        data: dict[str, Any],
        entity_id: str,
        unique_id: str | None,
        entity_enabled: bool,
        supports_write: bool,
    ) -> None:
        """Create the Calendar event device."""
        super().__init__(coordinator)
        self.calendar_id = calendar_id
        self._ignore_availability: bool = data.get(CONF_IGNORE_AVAILABILITY, False)
        self._event: CalendarEvent | None = None
        self._attr_name = data[CONF_NAME].capitalize()
        self._offset = data.get(CONF_OFFSET, DEFAULT_CONF_OFFSET)
        self.entity_id = entity_id
        self._attr_unique_id = unique_id
        self._attr_entity_registry_enabled_default = entity_enabled
        if supports_write:
            self._attr_supported_features = (
                CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
            )

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        return {"offset_reached": self.offset_reached}

    @property
    def offset_reached(self) -> bool:
        """Return whether or not the event offset was reached."""
        (event, offset_value) = self._event_with_offset()
        if event is not None and offset_value is not None:
            return is_offset_reached(event.start_datetime_local, offset_value)
        return False

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        (event, _) = self._event_with_offset()
        return event

    def _event_filter(self, event: Event) -> bool:
        """Return True if the event is visible."""
        if self._ignore_availability:
            return True
        return event.transparency == OPAQUE

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities. This is started as a
        # task to let if sync in the background without blocking startup
        self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self.coordinator.async_request_refresh(),
            "google.calendar-refresh",
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        result_items = await self.coordinator.async_get_events(start_date, end_date)
        return [
            _get_calendar_event(event)
            for event in filter(self._event_filter, result_items)
        ]

    def _event_with_offset(
        self,
    ) -> tuple[CalendarEvent | None, timedelta | None]:
        """Get the calendar event and offset if any."""
        if api_event := next(
            filter(
                self._event_filter,
                self.coordinator.upcoming or [],
            ),
            None,
        ):
            event = _get_calendar_event(api_event)
            if self._offset:
                (event.summary, offset_value) = extract_offset(
                    event.summary, self._offset
                )
            return event, offset_value
        return None, None

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""
        dtstart = kwargs[EVENT_START]
        dtend = kwargs[EVENT_END]
        start: DateOrDatetime
        end: DateOrDatetime
        if isinstance(dtstart, datetime):
            start = DateOrDatetime(
                date_time=dt_util.as_local(dtstart),
                timezone=str(dt_util.DEFAULT_TIME_ZONE),
            )
            end = DateOrDatetime(
                date_time=dt_util.as_local(dtend),
                timezone=str(dt_util.DEFAULT_TIME_ZONE),
            )
        else:
            start = DateOrDatetime(date=dtstart)
            end = DateOrDatetime(date=dtend)
        event = Event.parse_obj(
            {
                EVENT_SUMMARY: kwargs[EVENT_SUMMARY],
                "start": start,
                "end": end,
                EVENT_DESCRIPTION: kwargs.get(EVENT_DESCRIPTION),
            }
        )
        if location := kwargs.get(EVENT_LOCATION):
            event.location = location
        if rrule := kwargs.get(EVENT_RRULE):
            event.recurrence = [f"{RRULE_PREFIX}{rrule}"]

        try:
            await cast(
                CalendarSyncUpdateCoordinator, self.coordinator
            ).sync.store_service.async_add_event(event)
        except ApiException as err:
            raise HomeAssistantError(f"Error while creating event: {str(err)}") from err
        await self.coordinator.async_refresh()

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        range_value: Range = Range.NONE
        if recurrence_range == Range.THIS_AND_FUTURE:
            range_value = Range.THIS_AND_FUTURE
        await cast(
            CalendarSyncUpdateCoordinator, self.coordinator
        ).sync.store_service.async_delete_event(
            ical_uuid=uid,
            event_id=recurrence_id,
            recurrence_range=range_value,
        )
        await self.coordinator.async_refresh()


def _get_calendar_event(event: Event) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    rrule: str | None = None
    # Home Assistant expects a single RRULE: and all other rule types are unsupported or ignored
    if (
        len(event.recurrence) == 1
        and (raw_rule := event.recurrence[0])
        and raw_rule.startswith(RRULE_PREFIX)
    ):
        rrule = raw_rule.removeprefix(RRULE_PREFIX)
    return CalendarEvent(
        uid=event.ical_uuid,
        recurrence_id=event.id if event.recurring_event_id else None,
        rrule=rrule,
        summary=event.summary,
        start=event.start.value,
        end=event.end.value,
        description=event.description,
        location=event.location,
    )


async def async_create_event(entity: GoogleCalendarEntity, call: ServiceCall) -> None:
    """Add a new event to calendar."""
    start: DateOrDatetime | None = None
    end: DateOrDatetime | None = None
    hass = entity.hass

    if EVENT_IN in call.data:
        if EVENT_IN_DAYS in call.data[EVENT_IN]:
            now = datetime.now()

            start_in = now + timedelta(days=call.data[EVENT_IN][EVENT_IN_DAYS])
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

        elif EVENT_IN_WEEKS in call.data[EVENT_IN]:
            now = datetime.now()

            start_in = now + timedelta(weeks=call.data[EVENT_IN][EVENT_IN_WEEKS])
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

    elif EVENT_START_DATE in call.data and EVENT_END_DATE in call.data:
        start = DateOrDatetime(date=call.data[EVENT_START_DATE])
        end = DateOrDatetime(date=call.data[EVENT_END_DATE])

    elif EVENT_START_DATETIME in call.data and EVENT_END_DATETIME in call.data:
        start_dt = call.data[EVENT_START_DATETIME]
        end_dt = call.data[EVENT_END_DATETIME]
        start = DateOrDatetime(date_time=start_dt, timezone=str(hass.config.time_zone))
        end = DateOrDatetime(date_time=end_dt, timezone=str(hass.config.time_zone))

    if start is None or end is None:
        raise ValueError("Missing required fields to set start or end date/datetime")

    event = Event(
        summary=call.data[EVENT_SUMMARY],
        description=call.data[EVENT_DESCRIPTION],
        start=start,
        end=end,
    )
    if location := call.data.get(EVENT_LOCATION):
        event.location = location
    try:
        await cast(
            CalendarSyncUpdateCoordinator, entity.coordinator
        ).sync.api.async_create_event(
            entity.calendar_id,
            event,
        )
    except ApiException as err:
        raise HomeAssistantError(str(err)) from err
    entity.async_write_ha_state()
