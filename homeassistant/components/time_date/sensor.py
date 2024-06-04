"""Support for showing the date and the time."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISPLAY_OPTIONS, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import DOMAIN, OPTION_TYPES

_LOGGER = logging.getLogger(__name__)

TIME_STR_FORMAT = "%H:%M"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DISPLAY_OPTIONS, default=["time"]): vol.All(
            cv.ensure_list, [vol.In(OPTION_TYPES)]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Time and Date sensor."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")  # type: ignore[unreachable]
        return False

    if "beat" in config[CONF_DISPLAY_OPTIONS]:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_beat",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_beat",
            translation_placeholders={
                "config_key": "beat",
                "display_options": "display_options",
                "integration": DOMAIN,
            },
        )
        _LOGGER.warning("'beat': is deprecated and will be removed in version 2024.7")

    async_add_entities(
        [TimeDateSensor(variable) for variable in config[CONF_DISPLAY_OPTIONS]]
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Time & Date sensor."""

    async_add_entities(
        [TimeDateSensor(entry.options[CONF_DISPLAY_OPTIONS], entry.entry_id)]
    )


class TimeDateSensor(SensorEntity):
    """Implementation of a Time and Date sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _state: str | None = None
    unsub: CALLBACK_TYPE | None = None

    def __init__(self, option_type: str, entry_id: str | None = None) -> None:
        """Initialize the sensor."""
        self._attr_translation_key = option_type
        self.type = option_type
        object_id = "internet_time" if option_type == "beat" else option_type
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._attr_unique_id = option_type if entry_id else None

        self._update_internal_state(dt_util.utcnow())

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        if "date" in self.type and "time" in self.type:
            return "mdi:calendar-clock"
        if "date" in self.type:
            return "mdi:calendar"
        return "mdi:clock"

    @callback
    def async_start_preview(
        self,
        preview_callback: Callable[[str, Mapping[str, Any]], None],
    ) -> CALLBACK_TYPE:
        """Render a preview."""

        @callback
        def point_in_time_listener(time_date: datetime | None) -> None:
            """Update preview."""

            now = dt_util.utcnow()
            self._update_internal_state(now)
            self.unsub = async_track_point_in_utc_time(
                self.hass, point_in_time_listener, self.get_next_interval(now)
            )
            calculated_state = self._async_calculate_state()
            preview_callback(calculated_state.state, calculated_state.attributes)

        @callback
        def async_stop_preview() -> None:
            """Stop preview."""
            if self.unsub:
                self.unsub()
                self.unsub = None

        point_in_time_listener(None)
        return async_stop_preview

    async def async_added_to_hass(self) -> None:
        """Set up first update."""

        async def async_update_config(event: Event) -> None:
            """Handle core config update."""
            self._update_state_and_setup_listener()
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, async_update_config)
        )
        self._update_state_and_setup_listener()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel next update."""
        if self.unsub:
            self.unsub()
            self.unsub = None

    def get_next_interval(self, time_date: datetime) -> datetime:
        """Compute next time an update should occur."""
        if self.type == "date":
            tomorrow = dt_util.as_local(time_date) + timedelta(days=1)
            return dt_util.start_of_local_day(tomorrow)

        if self.type == "beat":
            # Add 1 hour because @0 beats is at 23:00:00 UTC.
            timestamp = dt_util.as_timestamp(time_date + timedelta(hours=1))
            interval = 86.4
        else:
            timestamp = dt_util.as_timestamp(time_date)
            interval = 60

        delta = interval - (timestamp % interval)
        next_interval = time_date + timedelta(seconds=delta)
        _LOGGER.debug("%s + %s -> %s (%s)", time_date, delta, next_interval, self.type)

        return next_interval

    def _update_internal_state(self, time_date: datetime) -> None:
        time = dt_util.as_local(time_date).strftime(TIME_STR_FORMAT)
        time_utc = time_date.strftime(TIME_STR_FORMAT)
        date = dt_util.as_local(time_date).date().isoformat()
        date_utc = time_date.date().isoformat()

        if self.type == "time":
            self._state = time
        elif self.type == "date":
            self._state = date
        elif self.type == "date_time":
            self._state = f"{date}, {time}"
        elif self.type == "date_time_utc":
            self._state = f"{date_utc}, {time_utc}"
        elif self.type == "time_date":
            self._state = f"{time}, {date}"
        elif self.type == "time_utc":
            self._state = time_utc
        elif self.type == "beat":
            # Calculate Swatch Internet Time.
            time_bmt = time_date + timedelta(hours=1)
            delta = timedelta(
                hours=time_bmt.hour,
                minutes=time_bmt.minute,
                seconds=time_bmt.second,
                microseconds=time_bmt.microsecond,
            )

            # Use integers to better handle rounding. For example,
            # int(63763.2/86.4) = 737 but 637632//864 = 738.
            beat = int(delta.total_seconds() * 10) // 864

            self._state = f"@{beat:03d}"
        elif self.type == "date_time_iso":
            self._state = dt_util.parse_datetime(
                f"{date} {time}", raise_on_error=True
            ).isoformat()

    def _update_state_and_setup_listener(self) -> None:
        """Update state and setup listener for next interval."""
        now = dt_util.utcnow()
        self._update_internal_state(now)
        self.unsub = async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval(now)
        )

    @callback
    def point_in_time_listener(self, time_date: datetime) -> None:
        """Get the latest data and update state."""
        self._update_state_and_setup_listener()
        self.async_write_ha_state()
