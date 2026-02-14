"""Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date as Date, datetime, time as Time, timedelta
import logging
from typing import Any
import zoneinfo

from py_rejseplan.dataclasses.departure import Departure

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import UnitOfTime
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt as dt_util

from .const import CONF_DEPARTURE_TYPE, CONF_DIRECTION, CONF_STOP_ID, DOMAIN
from .coordinator import RejseplanenConfigEntry, RejseplanenDataUpdateCoordinator
from .entity import RejseplanenEntity, RejseplanenEntityContext

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Buffer time after departure for cleanup
DEPARTURE_CLEANUP_BUFFER = timedelta(seconds=15)
COPENHAGEN_TZ = zoneinfo.ZoneInfo("Europe/Copenhagen")


@dataclass(kw_only=True, frozen=True)
class RejseplanenSensorEntityDescription(SensorEntityDescription):
    """Describes Rejseplanen sensor entity."""

    value_fn: Callable[
        [list[Departure], zoneinfo.ZoneInfo], StateType | datetime | None
    ]


def cph_to_tz(dt_date: Date, dt_time: Time, target_tz: zoneinfo.ZoneInfo) -> datetime:
    """Return a datetime in the target_tz, assuming input is Copenhagen local time."""
    cph_naive = datetime.combine(dt_date, dt_time)
    cph_aware = cph_naive.replace(tzinfo=COPENHAGEN_TZ)
    return cph_aware.astimezone(target_tz)


def _get_current_departures(
    departures: list[Departure], tz: zoneinfo.ZoneInfo
) -> list[Departure]:
    """Filter out past departures and return only current/future ones."""
    if not departures:
        return []

    now = dt_util.now(tz)

    current_departures = []
    for departure in departures:
        dep_time = _get_departure_timestamp(departure, tz)
        # Only include departures that haven't left yet (with small buffer)
        if dep_time and dep_time > now - DEPARTURE_CLEANUP_BUFFER:
            current_departures.append(departure)

    return current_departures


def _get_next_departure_cleanup_time(
    departures: list[Departure], tz: zoneinfo.ZoneInfo
) -> datetime | None:
    """Get the next time when departures should be filtered (first departure + buffer)."""
    current_departures = _get_current_departures(departures, tz)
    if not current_departures:
        return None

    now = dt_util.now(tz)
    for departure in current_departures:
        # Use realtime if available, otherwise planned time
        departure_datetime = _get_departure_timestamp(departure, tz)
        if not departure_datetime:
            continue

        if departure_datetime > now:
            # Schedule cleanup slightly after the departure time
            return departure_datetime + DEPARTURE_CLEANUP_BUFFER
    return None


def _get_departure_timestamp(
    departure: Departure | None, tz: zoneinfo.ZoneInfo
) -> datetime | None:
    """Get departure timestamp (realtime if available, otherwise planned)."""
    if departure is None:
        return None
    next_date = departure.rtDate or departure.date
    next_time = departure.rtTime or departure.time
    return cph_to_tz(next_date, next_time, tz)


def _get_delay_minutes(
    departure: Departure | None, tz: zoneinfo.ZoneInfo
) -> int | None:
    """Get delay minutes for the departure at index."""
    if departure is None:
        return None

    planned_datetime = cph_to_tz(departure.date, departure.time, tz)
    realtime_datetime = _get_departure_timestamp(departure, tz)
    if realtime_datetime is None:
        return None

    delay_seconds = (realtime_datetime - planned_datetime).total_seconds()
    delay_minutes = round(delay_seconds / 60) if delay_seconds != 0 else 0

    return max(0, delay_minutes)


# SENSORS tuple definition
SENSORS: tuple[RejseplanenSensorEntityDescription, ...] = (
    RejseplanenSensorEntityDescription(
        key="line",
        translation_key="line",
        value_fn=lambda departures, tz: (
            _get_current_departures(departures, tz)[0].name
            if _get_current_departures(departures, tz)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="departure_time",
        translation_key="departure_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda departures, tz: (
            _get_departure_timestamp(_get_current_departures(departures, tz)[0], tz)
            if _get_current_departures(departures, tz)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="delay",
        translation_key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda departures, tz: (
            _get_delay_minutes(_get_current_departures(departures, tz)[0], tz)
            if _get_current_departures(departures, tz)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="direction",
        translation_key="direction",
        value_fn=lambda departures, tz: (
            _get_current_departures(departures, tz)[0].direction
            if _get_current_departures(departures, tz)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="track",
        translation_key="track",
        value_fn=lambda departures, tz: (
            _get_current_departures(departures, tz)[0].rtTrack
            or _get_current_departures(departures, tz)[0].track
            if _get_current_departures(departures, tz)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="departures",
        translation_key="no_departures",
        value_fn=lambda departures, tz: len(_get_current_departures(departures, tz)),
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rejseplanen sensors (deprecated)."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "yaml_deprecated",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_deprecated",
    )
    _LOGGER.warning(
        "YAML configuration for Rejseplanen is deprecated. "
        "Please remove the rejseplanen entry from your configuration.yaml "
        "and set up the integration through the UI"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Rejseplanen sensors."""
    coordinator = config_entry.runtime_data

    # Process all subentries (stop configurations)
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "stop":
            continue

        async_add_entities(
            [
                RejseplanenTransportSensor(
                    coordinator=coordinator,
                    config=subentry,
                    entity_description=description,
                )
                for description in SENSORS
            ],
            config_subentry_id=subentry.subentry_id,
        )


class RejseplanenTransportSensor(RejseplanenEntity, SensorEntity):
    """Implementation of Rejseplanen transport sensor."""

    entity_description: RejseplanenSensorEntityDescription
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        coordinator: RejseplanenDataUpdateCoordinator,
        config: ConfigSubentry,
        entity_description: RejseplanenSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        context = RejseplanenEntityContext(
            stop_id=config.data[CONF_STOP_ID],
            name=config.title,
            subentry_id=config.subentry_id,
        )
        super().__init__(coordinator, context)
        self.entity_description = entity_description

        self._departure_cleanup_unsubscribe: CALLBACK_TYPE | None = None
        self._last_cleanup_time: datetime | None = None

        self._stop_id = context.stop_id
        self._direction = config.data[CONF_DIRECTION]
        self._departure_type = config.data[CONF_DEPARTURE_TYPE]
        self._attr_unique_id = f"{context.subentry_id}_{entity_description.key}"
        # Calculate bitflag for filtering
        self._departure_type_bitflag = coordinator.api.calculate_departure_type_bitflag(
            self._departure_type
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        # Use async_on_remove for proper cleanup registration
        self.async_on_remove(self._cancel_cleanup_trigger)
        self._schedule_next_cleanup()

    def _schedule_next_cleanup(self) -> None:
        """Schedule the next departure cleanup trigger."""
        self._cancel_cleanup_trigger()

        departures = self._get_filtered_departures()
        tz = dt_util.get_time_zone(self.hass.config.time_zone) or zoneinfo.ZoneInfo(
            "UTC"
        )
        cleanup_time = _get_next_departure_cleanup_time(departures, tz)

        if cleanup_time and cleanup_time != self._last_cleanup_time:
            # Only schedule if we have a departure and it's different from last time
            now = dt_util.utcnow()
            if cleanup_time > now:
                _LOGGER.debug(
                    "Scheduling departure cleanup for %s at %s",
                    self.entity_id,
                    cleanup_time,
                )
                self._departure_cleanup_unsubscribe = async_track_point_in_time(
                    self.hass, self._async_departure_cleanup, cleanup_time
                )
                self._last_cleanup_time = cleanup_time

    def _cancel_cleanup_trigger(self) -> None:
        """Cancel any scheduled cleanup trigger."""
        if self._departure_cleanup_unsubscribe:
            self._departure_cleanup_unsubscribe()
            self._departure_cleanup_unsubscribe = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        self._schedule_next_cleanup()

    @callback
    def _async_departure_cleanup(self, now: datetime) -> None:
        """Handle cleanup when a departure time has passed."""
        _LOGGER.debug("Processing departure cleanup for %s", self.entity_id)

        self.async_write_ha_state()
        self._schedule_next_cleanup()

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        departures = self._get_filtered_departures()
        tz = dt_util.get_time_zone(self.hass.config.time_zone) or zoneinfo.ZoneInfo(
            "UTC"
        )
        return self.entity_description.value_fn(departures, tz)


    def _get_filtered_departures(self) -> list[Departure]:
        """Get filtered departures based on the configured parameters."""
        return self.coordinator.get_filtered_departures(
            stop_id=self._stop_id,
            direction_filter=self._direction if self._direction else None,
            departure_type_filter=self._departure_type_bitflag,
        )
