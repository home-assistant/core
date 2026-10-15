"""Entities for the schedule integration."""

from collections.abc import Callable
from datetime import datetime, time, timedelta
import itertools
from typing import Literal, override

from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.collection import CollectionEntity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DATA,
    CONF_FROM,
    CONF_TO,
    DOMAIN,
    WEEKDAY_TO_CONF,
    ScheduleEntityCapabilityAttribute,
    ScheduleEntityStateAttribute,
)
from .schema import ENTITY_SCHEMA


class Schedule(CollectionEntity):
    """Schedule entity."""

    _entity_component_unrecorded_attributes = frozenset(
        {
            ScheduleEntityCapabilityAttribute.EDITABLE,
            ScheduleEntityStateAttribute.NEXT_EVENT,
        }
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
        self._attr_capability_attributes = {
            ScheduleEntityCapabilityAttribute.EDITABLE: editable
        }
        self._attr_icon = self._config.get(CONF_ICON)
        self._attr_name = self._config[CONF_NAME]
        self._attr_unique_id = self._config[CONF_ID]

        # Exclude any custom attributes that may be present
        # on time ranges from recording.
        self._unrecorded_attributes = self.all_custom_data_keys()
        self._Entity__combined_unrecorded_attributes = (
            self._entity_component_unrecorded_attributes | self._unrecorded_attributes
        )

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Schedule:
        """Return entity instance initialized from storage."""
        return cls(config, editable=True)

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Schedule:
        """Return entity instance initialized from yaml."""
        schedule = cls(config, editable=False)
        schedule.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        return schedule

    @override
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

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(self._clean_up_listener)
        self._update()

    def get_schedule(self) -> ConfigType:
        """Return the schedule."""
        return {d: self._config[d] for d in WEEKDAY_TO_CONF.values()}

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
            ScheduleEntityStateAttribute.NEXT_EVENT: next_event,
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
        data_keys: set[str] = set()

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
