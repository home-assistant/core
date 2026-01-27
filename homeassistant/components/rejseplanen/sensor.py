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
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DELAY_MINUTES,
    ATTR_DUE_AT,
    ATTR_DUE_IN,
    ATTR_FINAL_STOP,
    ATTR_IS_CANCELLED,
    ATTR_PLANNED_TIME,
    ATTR_REAL_TIME_AT,
    ATTR_REALTIME_TIME,
    ATTR_SCHEDULED_AT,
    ATTR_STOP_ID,
    ATTR_STOP_NAME,
    ATTR_TRACK,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
)
from .coordinator import RejseplanenConfigEntry, RejseplanenDataUpdateCoordinator
from .entity import RejseplanenEntity  # ✅ Import base entity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Buffer time after departure for cleanup
DEPARTURE_CLEANUP_BUFFER = timedelta(seconds=15)


@dataclass(kw_only=True, frozen=True)
class RejseplanenSensorEntityDescription(SensorEntityDescription):
    """Describes Rejseplanen sensor entity."""

    value_fn: Callable[[list[Departure]], StateType | datetime | None]
    attr_fn: Callable[[list[Departure]], dict[str, Any]] | None = None


# Define helper functions first, before SENSORS tuple
def _calculate_due_in(date: Date, time: Time) -> int:
    """Calculate due in minutes."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)
    departure_time = datetime.combine(date, time).replace(tzinfo=tz)
    due_in_seconds = (departure_time - now).total_seconds()
    return round(due_in_seconds / 60) if due_in_seconds > 0 else 0


def _get_current_departures(departures: list[Departure]) -> list[Departure]:
    """Filter out past departures and return only current/future ones."""
    if not departures:
        return []

    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    current_departures = []
    for departure in departures:
        # Use realtime if available, otherwise planned time
        departure_date = departure.rtDate or departure.date
        departure_time = departure.rtTime or departure.time
        departure_datetime = datetime.combine(departure_date, departure_time).replace(
            tzinfo=tz
        )

        # Only include departures that haven't left yet (with small buffer)
        if departure_datetime > now - DEPARTURE_CLEANUP_BUFFER:
            current_departures.append(departure)

    return current_departures


def _get_next_departure_cleanup_time(departures: list[Departure]) -> datetime | None:
    """Get the next time when departures should be filtered (first departure + buffer)."""
    current_departures = _get_current_departures(departures)
    if not current_departures:
        return None

    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    first_departure = current_departures[0]
    departure_date = first_departure.rtDate or first_departure.date
    departure_time = first_departure.rtTime or first_departure.time
    departure_datetime = datetime.combine(departure_date, departure_time).replace(
        tzinfo=tz
    )

    # Schedule cleanup slightly after the departure time
    return departure_datetime + DEPARTURE_CLEANUP_BUFFER


def _get_departure_timestamp(
    departures: list[Departure], index: int
) -> datetime | None:
    """Get departure timestamp (realtime if available, otherwise planned)."""
    current_departures = _get_current_departures(departures)

    if not current_departures or len(current_departures) <= index:
        return None

    departure = current_departures[index]
    next_date = departure.rtDate or departure.date
    next_time = departure.rtTime or departure.time

    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    return datetime.combine(next_date, next_time).replace(tzinfo=tz)


def _get_departure_attributes(
    departures: list[Departure], index: int
) -> dict[str, Any]:
    """Get attributes for single departure at index."""
    current_departures = _get_current_departures(departures)

    if not current_departures or len(current_departures) <= index:
        return _get_empty_departure_attributes()
    departure = current_departures[index]
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")

    planned_datetime = datetime.combine(departure.date, departure.time).replace(
        tzinfo=tz
    )
    realtime_datetime = datetime.combine(
        departure.rtDate or departure.date, departure.rtTime or departure.time
    ).replace(tzinfo=tz)

    delay_seconds = (realtime_datetime - planned_datetime).total_seconds()
    delay_minutes = round(delay_seconds / 60) if delay_seconds != 0 else 0
    is_cancelled = hasattr(departure, "cancelled") and departure.cancelled

    return {
        ATTR_STOP_ID: departure.stopExtId,
        ATTR_STOP_NAME: departure.name,
        ATTR_FINAL_STOP: departure.direction,
        ATTR_TRACK: departure.rtTrack or departure.track,
        ATTR_PLANNED_TIME: planned_datetime.isoformat(),
        ATTR_REALTIME_TIME: realtime_datetime.isoformat(),
        ATTR_DUE_IN: _calculate_due_in(
            departure.rtDate or departure.date, departure.rtTime or departure.time
        ),
        ATTR_DUE_AT: realtime_datetime.isoformat(),
        ATTR_SCHEDULED_AT: planned_datetime.isoformat(),
        ATTR_REAL_TIME_AT: realtime_datetime.isoformat(),
        ATTR_IS_CANCELLED: is_cancelled,
        ATTR_DELAY_MINUTES: delay_minutes,
        "has_realtime": departure.rtDate is not None or departure.rtTime is not None,
        "line_type": departure.type if hasattr(departure, "type") else None,
        "operator": departure.product.operator
        if hasattr(departure, "product") and hasattr(departure.product, "operator")
        else None,
    }


def _get_is_delayed(departures: list[Departure], index: int) -> bool:
    """Get whether the departure at index is delayed."""
    current_departures = _get_current_departures(departures)

    if not current_departures or len(current_departures) <= index:
        return False

    departure = current_departures[index]

    if departure.rtDate is None and departure.rtTime is None:
        return False

    planned_datetime = datetime.combine(departure.date, departure.time)
    realtime_datetime = datetime.combine(
        departure.rtDate or departure.date, departure.rtTime or departure.time
    )

    delay_seconds = (realtime_datetime - planned_datetime).total_seconds()
    delay_minutes = round(delay_seconds / 60) if delay_seconds != 0 else 0

    return delay_minutes > 0


def _get_delay_minutes(departures: list[Departure], index: int) -> int | None:
    """Get delay minutes for the departure at index."""
    current_departures = _get_current_departures(departures)

    if not current_departures or len(current_departures) <= index:
        return None

    departure = current_departures[index]
    planned_datetime = datetime.combine(departure.date, departure.time)
    realtime_datetime = datetime.combine(
        departure.rtDate or departure.date, departure.rtTime or departure.time
    )

    delay_seconds = (realtime_datetime - planned_datetime).total_seconds()
    delay_minutes = round(delay_seconds / 60) if delay_seconds != 0 else 0

    return max(0, delay_minutes)


def _format_departures_for_dashboard(
    departures: list[Departure], tz: zoneinfo.ZoneInfo
) -> list[dict[str, Any]]:
    """Format a list of Departure objects for the dashboard.

    Returns a list of dicts with keys:
      - index, line, direction, track, due_in, due_in_text,
      - scheduled_time, realtime_time, is_delayed, delay_minutes,
      - delay_text, is_cancelled, status_icon, line_type
    """
    departures_data: list[dict[str, Any]] = []
    now = datetime.now(tz)

    for i, departure in enumerate(departures):
        planned_datetime = datetime.combine(departure.date, departure.time).replace(
            tzinfo=tz
        )
        realtime_datetime = datetime.combine(
            departure.rtDate or departure.date, departure.rtTime or departure.time
        ).replace(tzinfo=tz)

        # Calculate delay and timing info
        delay_seconds = (realtime_datetime - planned_datetime).total_seconds()
        delay_minutes = round(delay_seconds / 60) if delay_seconds != 0 else 0
        is_delayed = delay_minutes > 0

        due_in_seconds = (realtime_datetime - now).total_seconds()
        due_in = round(due_in_seconds / 60) if due_in_seconds > 0 else 0

        is_cancelled = hasattr(departure, "cancelled") and departure.cancelled

        departure_info = {
            "index": i,
            "line": departure.name,
            "direction": departure.direction,
            "track": departure.rtTrack or departure.track,
            "due_in": due_in,
            "due_in_text": f"{due_in} min" if due_in > 0 else "Now",
            "scheduled_time": planned_datetime.strftime("%H:%M"),
            "realtime_time": realtime_datetime.strftime("%H:%M"),
            "is_delayed": is_delayed,
            "delay_minutes": delay_minutes if is_delayed else 0,
            "delay_text": f"+{delay_minutes} min" if is_delayed else None,
            "is_cancelled": is_cancelled,
            "status_icon": "🔴" if is_delayed else "🟢",
            "line_type": departure.type if hasattr(departure, "type") else None,
        }

        departures_data.append(departure_info)

    return departures_data


def _get_departures_list_attributes(departures: list[Departure]) -> dict[str, Any]:
    """Get structured departures data for dashboard display."""
    current_departures = _get_current_departures(departures)

    if not current_departures:
        return {"departures": [], "last_updated": datetime.now().isoformat()}

    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")

    return {
        "total_departures": len(current_departures),
        "last_updated": datetime.now(tz).isoformat(),
    }


def _get_empty_departure_attributes() -> dict[str, Any]:
    """Return empty attributes structure when no departure data available."""
    return {
        ATTR_STOP_ID: None,
        ATTR_STOP_NAME: None,
        ATTR_FINAL_STOP: None,
        ATTR_TRACK: None,
        ATTR_PLANNED_TIME: None,
        ATTR_REALTIME_TIME: None,
        ATTR_DUE_IN: None,
        ATTR_DUE_AT: None,
        ATTR_SCHEDULED_AT: None,
        ATTR_REAL_TIME_AT: None,
        ATTR_IS_CANCELLED: None,
        ATTR_DELAY_MINUTES: None,
        "has_realtime": None,
        "line_type": None,
        "operator": None,
    }


# SENSORS tuple definition
SENSORS: tuple[RejseplanenSensorEntityDescription, ...] = (
    RejseplanenSensorEntityDescription(
        key="line",
        translation_key="line",
        value_fn=lambda departures: (
            _get_current_departures(departures)[0].name
            if _get_current_departures(departures)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="departure_time",
        translation_key="departure_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda departures: (
            _get_departure_timestamp(departures, 0) if departures else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="delay",
        translation_key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda departures: (
            _get_delay_minutes(departures, 0) if departures else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="direction",
        translation_key="direction",
        value_fn=lambda departures: (
            _get_current_departures(departures)[0].direction
            if _get_current_departures(departures)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="track",
        translation_key="track",
        value_fn=lambda departures: (
            _get_current_departures(departures)[0].rtTrack
            or _get_current_departures(departures)[0].track
            if _get_current_departures(departures)
            else None
        ),
    ),
    RejseplanenSensorEntityDescription(
        key="departures",
        translation_key="no_departures",
        value_fn=lambda departures: len(_get_current_departures(departures)),
        attr_fn=_get_departures_list_attributes,
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
            ]
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
        super().__init__(coordinator, int(config.data[CONF_STOP_ID]))
        self.entity_description = entity_description

        self._departure_cleanup_unsubscribe: CALLBACK_TYPE | None = None
        self._last_cleanup_time: datetime | None = None

        self._stop_id = int(config.data[CONF_STOP_ID])
        self._route = config.data[CONF_ROUTE]
        self._direction = config.data[CONF_DIRECTION]
        self._departure_type = config.data[CONF_DEPARTURE_TYPE]
        self._attr_unique_id = f"{config.subentry_id}_{entity_description.key}"

        # Calculate bitflag for filtering
        self._departure_type_bitflag = coordinator.api.calculate_departure_type_bitflag(
            self._departure_type
        )
        # Create a device for this configured stop using the configuration
        # values so the device entry contains useful metadata for the stop.
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, config.subentry_id)},
            name=config.data.get("name"),
            manufacturer="Rejseplanen",
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
        cleanup_time = _get_next_departure_cleanup_time(departures)

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
        return self.entity_description.value_fn(departures)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        base_attributes = {ATTR_STOP_ID: self._stop_id}

        if self.entity_description.attr_fn:
            departures = self._get_filtered_departures()
            additional_attrs = self.entity_description.attr_fn(departures)
            base_attributes.update(additional_attrs)

        return base_attributes

    def _get_filtered_departures(self) -> list[Departure]:
        """Get filtered departures based on the configured parameters."""
        return self.coordinator.get_filtered_departures(
            stop_id=self._stop_id,
            route_filter=self._route if self._route else None,
            direction_filter=self._direction if self._direction else None,
            departure_type_filter=self._departure_type_bitflag,
        )
