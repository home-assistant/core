"""Support for representing current time of the day as binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import TYPE_CHECKING, Any, Literal, TypeGuard

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AFTER,
    CONF_BEFORE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import get_astral_event_date, get_astral_event_next
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AFTER_OFFSET,
    CONF_AFTER_TIME,
    CONF_BEFORE_OFFSET,
    CONF_BEFORE_TIME,
)

type SunEventType = Literal["sunrise", "sunset"]

_LOGGER = logging.getLogger(__name__)

ATTR_AFTER = "after"
ATTR_BEFORE = "before"
ATTR_NEXT_UPDATE = "next_update"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AFTER): vol.Any(cv.time, vol.All(vol.Lower, cv.sun_event)),
        vol.Required(CONF_BEFORE): vol.Any(cv.time, vol.All(vol.Lower, cv.sun_event)),
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_AFTER_OFFSET, default=timedelta(0)): cv.time_period,
        vol.Optional(CONF_BEFORE_OFFSET, default=timedelta(0)): cv.time_period,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Times of the Day config entry."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")  # type: ignore[unreachable]
        return

    after = cv.time(config_entry.options[CONF_AFTER_TIME])
    after_offset = timedelta(0)
    before = cv.time(config_entry.options[CONF_BEFORE_TIME])
    before_offset = timedelta(0)
    name = config_entry.title
    unique_id = config_entry.entry_id

    async_add_entities(
        [TodSensor(name, after, after_offset, before, before_offset, unique_id)]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ToD sensors."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")  # type: ignore[unreachable]
        return

    after = config[CONF_AFTER]
    after_offset = config[CONF_AFTER_OFFSET]
    before = config[CONF_BEFORE]
    before_offset = config[CONF_BEFORE_OFFSET]
    name = config[CONF_NAME]
    unique_id = config.get(CONF_UNIQUE_ID)
    sensor = TodSensor(name, after, after_offset, before, before_offset, unique_id)

    async_add_entities([sensor])


def _is_sun_event(sun_event: time | SunEventType) -> TypeGuard[SunEventType]:
    """Return true if event is sun event not time."""
    return sun_event in (SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)


class TodSensor(BinarySensorEntity):
    """Time of the Day Sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        after: time,
        after_offset: timedelta,
        before: time,
        before_offset: timedelta,
        unique_id: str | None,
    ) -> None:
        """Init the ToD Sensor..."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._time_before: datetime | None = None
        self._time_after: datetime | None = None
        self._next_update: datetime | None = None
        self._after_offset = after_offset
        self._before_offset = before_offset
        self._before = before
        self._after = after
        self._unsub_update: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool:
        """Return True is sensor is on."""
        if TYPE_CHECKING:
            assert self._time_after is not None
            assert self._time_before is not None
        if self._time_after < self._time_before:
            return self._time_after <= dt_util.utcnow() < self._time_before
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        if TYPE_CHECKING:
            assert self._time_after is not None
            assert self._time_before is not None
            assert self._next_update is not None
        if time_zone := dt_util.get_default_time_zone():
            return {
                ATTR_AFTER: self._time_after.astimezone(time_zone).isoformat(),
                ATTR_BEFORE: self._time_before.astimezone(time_zone).isoformat(),
                ATTR_NEXT_UPDATE: self._next_update.astimezone(time_zone).isoformat(),
            }
        return None

    def _naive_time_to_utc_datetime(self, naive_time: time) -> datetime:
        """Convert naive time from config to utc_datetime with current day."""
        # get the current local date from utc time
        current_local_date = (
            dt_util.utcnow().astimezone(dt_util.get_default_time_zone()).date()
        )
        # calculate utc datetime corresponding to local time
        return dt_util.as_utc(datetime.combine(current_local_date, naive_time))

    def _calculate_boundary_time(self) -> None:
        """Calculate internal absolute time boundaries."""
        nowutc = dt_util.utcnow()
        # If after value is a sun event instead of absolute time
        if _is_sun_event(self._after):
            # Calculate the today's event utc time or
            # if not available take next
            after_event_date = get_astral_event_date(
                self.hass, self._after, nowutc
            ) or get_astral_event_next(self.hass, self._after, nowutc)
        else:
            # Convert local time provided to UTC today
            # datetime.combine(date, time, tzinfo) is not supported
            # in python 3.5. The self._after is provided
            # with hass configured TZ not system wide
            after_event_date = self._naive_time_to_utc_datetime(self._after)

        self._time_after = after_event_date

        # If before value is a sun event instead of absolute time
        if _is_sun_event(self._before):
            # Calculate the today's event utc time or  if not available take
            # next
            before_event_date = get_astral_event_date(
                self.hass, self._before, nowutc
            ) or get_astral_event_next(self.hass, self._before, nowutc)
            # Before is earlier than after
            if before_event_date < after_event_date:
                # Take next day for before
                before_event_date = get_astral_event_next(
                    self.hass, self._before, after_event_date
                )
        else:
            # Convert local time provided to UTC today, see above
            before_event_date = self._naive_time_to_utc_datetime(self._before)

            # It is safe to add timedelta days=1 to UTC as there is no DST
            if before_event_date < after_event_date + self._after_offset:
                before_event_date += timedelta(days=1)

        self._time_before = before_event_date

        # We are calculating the _time_after value assuming that it will happen today
        # But that is not always true, e.g. after 23:00, before 12:00 and now is 10:00
        # If _time_before and _time_after are ahead of nowutc:
        # _time_before is set to 12:00 next day
        # _time_after is set to 23:00 today
        # nowutc is set to 10:00 today

        if (
            not _is_sun_event(self._after)
            and self._time_after > nowutc
            and self._time_before > nowutc + timedelta(days=1)
        ):
            # remove one day from _time_before and _time_after
            self._time_after -= timedelta(days=1)
            self._time_before -= timedelta(days=1)

        # Add offset to utc boundaries according to the configuration
        self._time_after += self._after_offset
        self._time_before += self._before_offset

    def _add_one_dst_aware_day(self, a_date: datetime, target_time: time) -> datetime:
        """Add 24 hours (1 day) but account for DST."""
        tentative_new_date = a_date + timedelta(days=1)
        tentative_new_date = dt_util.as_local(tentative_new_date)
        tentative_new_date = tentative_new_date.replace(
            hour=target_time.hour, minute=target_time.minute
        )
        # The following call addresses missing time during DST jumps
        return dt_util.find_next_time_expression_time(
            tentative_new_date,
            dt_util.parse_time_expression("*", 0, 59),
            dt_util.parse_time_expression("*", 0, 59),
            dt_util.parse_time_expression("*", 0, 23),
        )

    def _turn_to_next_day(self) -> None:
        """Turn to to the next day."""
        if TYPE_CHECKING:
            assert self._time_after is not None
            assert self._time_before is not None
        if _is_sun_event(self._after):
            self._time_after = get_astral_event_next(
                self.hass, self._after, self._time_after - self._after_offset
            )
            self._time_after += self._after_offset
        else:
            # Offset is already there
            self._time_after = self._add_one_dst_aware_day(
                self._time_after, self._after
            )

        if _is_sun_event(self._before):
            self._time_before = get_astral_event_next(
                self.hass, self._before, self._time_before - self._before_offset
            )
            self._time_before += self._before_offset
        else:
            # Offset is already there
            self._time_before = self._add_one_dst_aware_day(
                self._time_before, self._before
            )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        self._calculate_boundary_time()
        self._calculate_next_update()

        @callback
        def _clean_up_listener() -> None:
            if self._unsub_update is not None:
                self._unsub_update()
                self._unsub_update = None

        self.async_on_remove(_clean_up_listener)

        if TYPE_CHECKING:
            assert self._next_update is not None
        self._unsub_update = event.async_track_point_in_utc_time(
            self.hass, self._point_in_time_listener, self._next_update
        )

    def _calculate_next_update(self) -> None:
        """Datetime when the next update to the state."""
        if TYPE_CHECKING:
            assert self._time_after is not None
            assert self._time_before is not None
        now = dt_util.utcnow()
        if now < self._time_after:
            self._next_update = self._time_after
            return
        if now < self._time_before:
            self._next_update = self._time_before
            return
        self._turn_to_next_day()
        self._next_update = self._time_after

    @callback
    def _point_in_time_listener(self, now: datetime) -> None:
        """Run when the state of the sensor should be updated."""
        self._calculate_next_update()
        self.async_write_ha_state()

        if TYPE_CHECKING:
            assert self._next_update is not None

        self._unsub_update = event.async_track_point_in_utc_time(
            self.hass, self._point_in_time_listener, self._next_update
        )
