"""Support for schedules in Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import itertools
from typing import Any, Literal

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.collection import (
    CollectionEntity,
    DictStorageCollection,
    DictStorageCollectionWebsocket,
    IDManager,
    SerializedStorageCollection,
    YamlCollection,
    sync_entity_lifecycle,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_NEXT_EVENT,
    CONF_ALL_DAYS,
    CONF_DATA,
    CONF_FROM,
    CONF_TO,
    DOMAIN,
    LOGGER,
    WEEKDAY_TO_CONF,
)

STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 1


def valid_schedule(schedule: list[dict[str, str]]) -> list[dict[str, str]]:
    """Validate the schedule of time ranges.

    Ensure they have no overlap and the end time is greater than the start time.
    """
    # Empty schedule is valid
    if not schedule:
        return schedule

    # Sort the schedule by start times
    schedule = sorted(schedule, key=lambda time_range: time_range[CONF_FROM])

    # Check if the start time of the next event is before the end time of the previous event
    previous_to = None
    for time_range in schedule:
        if time_range[CONF_FROM] >= time_range[CONF_TO]:
            raise vol.Invalid(
                f"Invalid time range, from {time_range[CONF_FROM]} is after"
                f" {time_range[CONF_TO]}"
            )

        # Check if the from time of the event is after the to time of the previous event
        if previous_to is not None and previous_to > time_range[CONF_FROM]:  # type: ignore[unreachable]
            raise vol.Invalid("Overlapping times found in schedule")

        previous_to = time_range[CONF_TO]

    return schedule


def deserialize_to_time(value: Any) -> Any:
    """Convert 24:00 and 24:00:00 to time.max."""
    if not isinstance(value, str):
        return cv.time(value)

    parts = value.split(":")
    if len(parts) < 2:
        return cv.time(value)
    hour = int(parts[0])
    minute = int(parts[1])

    if hour == 24 and minute == 0:
        return time.max

    return cv.time(value)


def serialize_to_time(value: Any) -> Any:
    """Convert time.max to 24:00:00."""
    if value == time.max:
        return "24:00:00"
    return vol.Coerce(str)(value)


BASE_SCHEMA: VolDictType = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_ICON): cv.icon,
}

# Extra data that the user can set on each time range
CUSTOM_DATA_SCHEMA = vol.Schema({str: vol.Any(bool, str, int, float)})

TIME_RANGE_SCHEMA: VolDictType = {
    vol.Required(CONF_FROM): cv.time,
    vol.Required(CONF_TO): deserialize_to_time,
    vol.Optional(CONF_DATA): CUSTOM_DATA_SCHEMA,
}

# Serialize time in validated config
STORAGE_TIME_RANGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FROM): vol.Coerce(str),
        vol.Required(CONF_TO): serialize_to_time,
        vol.Optional(CONF_DATA): CUSTOM_DATA_SCHEMA,
    }
)

SCHEDULE_SCHEMA: VolDictType = {
    vol.Optional(day, default=[]): vol.All(
        cv.ensure_list, [TIME_RANGE_SCHEMA], valid_schedule
    )
    for day in CONF_ALL_DAYS
}
STORAGE_SCHEDULE_SCHEMA: VolDictType = {
    vol.Optional(day, default=[]): vol.All(
        cv.ensure_list, [TIME_RANGE_SCHEMA], valid_schedule, [STORAGE_TIME_RANGE_SCHEMA]
    )
    for day in CONF_ALL_DAYS
}

# Validate YAML config
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(vol.All(BASE_SCHEMA | SCHEDULE_SCHEMA))},
    extra=vol.ALLOW_EXTRA,
)
# Validate storage config
STORAGE_SCHEMA = vol.Schema(
    {vol.Required(CONF_ID): cv.string} | BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA
)
# Validate + transform entity config
ENTITY_SCHEMA = vol.Schema(
    {vol.Required(CONF_ID): cv.string} | BASE_SCHEMA | SCHEDULE_SCHEMA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up a schedule."""
    component = EntityComponent[Schedule](LOGGER, DOMAIN, hass)

    id_manager = IDManager()

    yaml_collection = YamlCollection(LOGGER, id_manager)
    sync_entity_lifecycle(hass, DOMAIN, DOMAIN, component, yaml_collection, Schedule)

    storage_collection = ScheduleStorageCollection(
        Store(
            hass,
            key=DOMAIN,
            version=STORAGE_VERSION,
            minor_version=STORAGE_VERSION_MINOR,
        ),
        id_manager,
    )
    sync_entity_lifecycle(hass, DOMAIN, DOMAIN, component, storage_collection, Schedule)

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    DictStorageCollectionWebsocket(
        storage_collection,
        DOMAIN,
        DOMAIN,
        BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA,
        BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA,
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload(skip_reset=True)
        if conf is None:
            conf = {DOMAIN: {}}
        await yaml_collection.async_load(
            [{CONF_ID: id_, **cfg} for id_, cfg in conf.get(DOMAIN, {}).items()]
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
    )

    return True


class ScheduleStorageCollection(DictStorageCollection):
    """Schedules stored in storage."""

    SCHEMA = vol.Schema(BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        self.SCHEMA(data)
        return data

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        name: str = info[CONF_NAME]
        return name

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        self.SCHEMA(update_data)
        return item | update_data

    async def _async_load_data(self) -> SerializedStorageCollection | None:
        """Load the data."""
        if data := await super()._async_load_data():
            data["items"] = [STORAGE_SCHEMA(item) for item in data["items"]]
        return data


class Schedule(CollectionEntity):
    """Schedule entity."""

    _entity_component_unrecorded_attributes = frozenset(
        {ATTR_EDITABLE, ATTR_NEXT_EVENT}
    )

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state: Literal["on", "off"]
    _config: ConfigType
    _next: datetime
    _unsub_update: Callable[[], None] | None = None

    def __init__(self, config: ConfigType, editable: bool) -> None:
        """Initialize a schedule."""
        self._config = ENTITY_SCHEMA(config)
        self._attr_capability_attributes = {ATTR_EDITABLE: editable}
        self._attr_icon = self._config.get(CONF_ICON)
        self._attr_name = self._config[CONF_NAME]
        self._attr_unique_id = self._config[CONF_ID]

        # Exclude any custom attributes that may be present on time ranges from recording.
        self._unrecorded_attributes = self.all_custom_data_keys()
        self._Entity__combined_unrecorded_attributes = (
            self._entity_component_unrecorded_attributes | self._unrecorded_attributes
        )

    @classmethod
    def from_storage(cls, config: ConfigType) -> Schedule:
        """Return entity instance initialized from storage."""
        return cls(config, editable=True)

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Schedule:
        """Return entity instance initialized from yaml."""
        schedule = cls(config, editable=False)
        schedule.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        return schedule

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = ENTITY_SCHEMA(config)
        self._attr_icon = config.get(CONF_ICON)
        self._attr_name = config[CONF_NAME]
        self._clean_up_listener()
        self._update()

    @callback
    def _clean_up_listener(self) -> None:
        """Remove the update timer."""
        if self._unsub_update is not None:
            self._unsub_update()
            self._unsub_update = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(self._clean_up_listener)
        self._update()

    @callback
    def _update(self, _: datetime | None = None) -> None:
        """Update the states of the schedule."""
        now = dt_util.now()
        todays_schedule = self._config.get(WEEKDAY_TO_CONF[now.weekday()], [])

        # Determine current schedule state
        for time_range in todays_schedule:
            # The current time should be greater or equal to CONF_FROM.
            if now.time() < time_range[CONF_FROM]:
                continue
            # The current time should be smaller (and not equal) to CONF_TO.
            # Note that any time in the day is treated as smaller than time.max.
            if now.time() < time_range[CONF_TO] or time_range[CONF_TO] == time.max:
                self._attr_state = STATE_ON
                current_data = time_range.get(CONF_DATA)
                break
        else:
            self._attr_state = STATE_OFF
            current_data = None

        # Find next event in the schedule, loop over each day (starting with
        # the current day) until the next event has been found.
        next_event = None
        for day in range(8):  # 8 because we need to search today's weekday next week
            day_schedule = self._config.get(
                WEEKDAY_TO_CONF[(now.weekday() + day) % 7], []
            )
            times = sorted(
                itertools.chain(
                    *[
                        [time_range[CONF_FROM], time_range[CONF_TO]]
                        for time_range in day_schedule
                    ]
                )
            )

            if next_event := next(
                (
                    possible_next_event
                    for timestamp in times
                    if (
                        possible_next_event := (
                            datetime.combine(now.date(), timestamp, tzinfo=now.tzinfo)
                            + timedelta(days=day)
                            if timestamp != time.max
                            # Special case for midnight of the following day.
                            else datetime.combine(now.date(), time(), tzinfo=now.tzinfo)
                            + timedelta(days=day + 1)
                        )
                    )
                    > now
                ),
                None,
            ):
                # We have found the next event in this day, stop searching.
                break

        self._attr_extra_state_attributes = {
            ATTR_NEXT_EVENT: next_event,
        }

        if current_data:
            # Add each key/value pair in the data to the entity's state attributes
            self._attr_extra_state_attributes.update(current_data)

        self.async_write_ha_state()

        if next_event:
            self._unsub_update = async_track_point_in_utc_time(
                self.hass,
                self._update,
                next_event,
            )

    def all_custom_data_keys(self) -> frozenset[str]:
        """Return the set of all currently used custom data attribute keys."""
        data_keys = set()

        for weekday in WEEKDAY_TO_CONF.values():
            if not (weekday_config := self._config.get(weekday)):
                continue  # this weekday is not configured

            for time_range in weekday_config:
                time_range_custom_data = time_range.get(CONF_DATA)

                if not time_range_custom_data or not isinstance(
                    time_range_custom_data, dict
                ):
                    continue  # this time range has no custom data, or it is not a dict

                data_keys.update(time_range_custom_data.keys())

        return frozenset(data_keys)
