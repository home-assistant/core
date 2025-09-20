"""Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date as Date, datetime, time as Time, timedelta
import logging
from typing import Any
import zoneinfo

from py_rejseplan.dataclasses.departure import Departure

from homeassistant import const
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DUE_AT,
    ATTR_DUE_IN,
    ATTR_FINAL_STOP,
    ATTR_REAL_TIME_AT,
    ATTR_SCHEDULED_AT,
    ATTR_STOP_ID,
    ATTR_STOP_NAME,
    ATTR_TRACK,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_ROUTE,
    CONF_STOP_ID,
    DEFAULT_STOP_NAME,
    DOMAIN,
    TransportClass,
)
from .coordinator import RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Rejseplanen transport sensor."""

    _LOGGER.info(
        "Setting up Rejseplanen transport sensor for entry: %s", config_entry.entry_id
    )

    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {}

    entry_data = hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    coordinator = entry_data.get("coordinator")

    # Only add the updater status sensor for the main entry
    if config_entry.domain == DOMAIN:
        async_add_entities(
            [RejseplanenDiagnosticSensor(coordinator, config_entry.entry_id)]
        )

    for subentry_id, subentry in config_entry.subentries.items():
        _LOGGER.debug("Subentry %s with data: %s", subentry_id, subentry.data)

        entry_data = hass.data[DOMAIN][config_entry.entry_id]
        coordinator = entry_data["coordinator"]

        config = subentry.data
        name = config.get(CONF_NAME, DEFAULT_STOP_NAME)
        stop_id = int(config[CONF_STOP_ID])
        route = config.get(CONF_ROUTE, [])
        direction = config.get(CONF_DIRECTION, [])
        departure_type = config.get(CONF_DEPARTURE_TYPE, [])

        async_add_entities(
            [
                RejseplanenTransportSensor(
                    coordinator=coordinator,
                    stop_id=stop_id,
                    entry_id=coordinator.config_entry.entry_id,
                    name=name,
                    route=route,
                    direction=direction,
                    departure_type=departure_type,
                )
            ],
            config_subentry_id=subentry_id,
        )

    await coordinator.async_config_entry_first_refresh()


def _service_device_info(entry_id: str) -> DeviceInfo:
    """Device representing the Rejseplanen service."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Rejseplanen",
        manufacturer="Rejseplanen",
        model="Public transport API",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://www.rejseplanen.dk/",
    )


def _stop_device_info(entry_id: str, stop_id: int, stop_name: str | None) -> DeviceInfo:
    """Child device for a specific stop, grouped via the service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}-stop-{stop_id}")},
        name=stop_name or f"Stop {stop_id}",
        via_device=(DOMAIN, entry_id),  # Parent = service device
    )


class RejseplanenTransportSensor(SensorEntity):
    """Implementation of Rejseplanen transport sensor."""

    _attr_attribution = "Data provided by rejseplanen.dk"
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        coordinator: RejseplanenDataUpdateCoordinator,
        stop_id: int,
        entry_id: str,
        route: list[str],
        direction: list[str],
        departure_type: list[str],
        name: str | None,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator: RejseplanenDataUpdateCoordinator = coordinator
        self._stop_id: int = stop_id
        self._route: list[str] = route
        self._direction: list[str] = direction
        self._departure_type: list[str] = departure_type
        self._attr_name: str | None = name
        self.coordinator.add_stop_id(stop_id)
        self._unsub_interval: Callable[[], None] | None = None
        self._attr_unique_id = f"{stop_id}_{name}_{departure_type}"
        self._attr_device_info = _stop_device_info(entry_id, stop_id, name)

        self._departure_type_bitflag = self._calculate_departure_type_bitflag(
            departure_type
        )
        """Initialize the sensor's state."""
        self._attr_native_unit_of_measurement = const.UnitOfTime.MINUTES
        self._attr_native_value = self._compute_native_value()

    def _calculate_departure_type_bitflag(self, departure_types: list) -> int | None:
        """Calculate bitflag from departure type list."""
        if not departure_types:
            return None

        bitflag = 0
        for transport_class in departure_types:
            if isinstance(transport_class, int):
                # If already an int (TransportClass enum value)
                bitflag |= transport_class
            elif isinstance(transport_class, TransportClass):
                # If TransportClass enum instance
                bitflag |= transport_class.value
            elif isinstance(transport_class, str):
                # If string, try to convert to TransportClass enum
                try:
                    enum_value = TransportClass[transport_class.upper()]
                    bitflag |= enum_value.value
                except KeyError:
                    _LOGGER.warning("Unknown departure type: %s", transport_class)
            else:
                _LOGGER.warning("Invalid departure type format: %s", transport_class)

        return bitflag if bitflag > 0 else None

    def _compute_native_value(self) -> StateType:
        """Return the state of the sensor."""
        departures: list[Departure] = self._get_filtered_departures()
        if departures:
            next_departure = departures[0]
            next_date = next_departure.rtDate or next_departure.date
            next_time = next_departure.rtTime or next_departure.time
            return self.due_in(date=next_date, time=next_time)
        return None

    def _compute_extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        departures: list[Departure] = self._get_filtered_departures()
        if not departures:
            return {ATTR_STOP_ID: self._stop_id}
        attributes: dict[str, Any] = {}

        next_departure: Departure = departures[0]
        next_date = next_departure.rtDate or next_departure.date
        next_time = next_departure.rtTime or next_departure.time
        next_track = next_departure.rtTrack or next_departure.track
        attributes.update(
            {
                ATTR_STOP_ID: self._stop_id,
                ATTR_STOP_NAME: next_departure.name,
                ATTR_FINAL_STOP: next_departure.direction,
                ATTR_DUE_IN: self.due_in(date=next_date, time=next_time),
                ATTR_DUE_AT: datetime.combine(next_date, next_time).isoformat(),
                ATTR_SCHEDULED_AT: datetime.combine(
                    next_departure.date, next_departure.time
                ).isoformat(),
                ATTR_REAL_TIME_AT: datetime.combine(next_date, next_time).isoformat(),
                ATTR_TRACK: next_track,
            }
        )
        if len(departures) > 1:
            attributes["next_departures"] = self.parse_next_departures(departures[1:])

        return attributes

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added to hass."""
        await super().async_added_to_hass()
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._handle_minute_tick,
            timedelta(minutes=1),
            name=f"rejseplanen_{self._attr_unique_id}_minute_tick",
        )
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal of the sensor from Home Assistant."""
        _LOGGER.debug("Removing sensor %s from coordinator", self._attr_unique_id)
        self.coordinator.remove_stop_id(self._stop_id)
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
            _LOGGER.debug(
                "Unsubscribed from minute tick for sensor %s", self._attr_unique_id
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Callback triggered when the coordinator updates data.

        This method is registered with the update coordinator and called whenever
        new data is fetched for the configured stop. It ensures the entity state
        is updated in Home Assistant after each coordinator refresh.
        """
        _LOGGER.debug(
            "Coordinator update callback triggered for sensor %s", self._attr_unique_id
        )
        self._attr_native_value = self._compute_native_value()
        self._attr_extra_state_attributes = self._compute_extra_state_attributes()
        self.async_write_ha_state()

    @callback
    def _handle_minute_tick(self, now):
        """Call every minute to update the state."""
        _LOGGER.debug(
            "Minute tick callback triggered for sensor %s at %s",
            self._attr_unique_id,
            now.isoformat(),
        )
        self.async_write_ha_state()

    def _get_filtered_departures(self) -> list[Departure]:
        """Get filtered departures based on the configured parameters."""
        route_filter = self._route if self._route else None
        direction_filter = self._direction if self._direction else None

        return self.coordinator.get_filtered_departures(
            stop_id=self._stop_id,
            route_filter=route_filter,
            direction_filter=direction_filter,
            departure_type_filter=self._departure_type_bitflag,
        )

    @staticmethod
    def parse_next_departures(departures: list[Departure]) -> list[dict[str, Any]]:
        """Parse the next departures into a list of dictionaries."""
        parsed_departures = []
        for departure in departures:
            parsed_departure = {
                ATTR_STOP_ID: departure.stopExtId,
                ATTR_STOP_NAME: departure.name,
                ATTR_FINAL_STOP: departure.direction,
                ATTR_DUE_IN: RejseplanenTransportSensor.due_in(
                    departure.rtTime or departure.time,
                    departure.rtDate or departure.date,
                ),
                ATTR_DUE_AT: datetime.combine(
                    departure.date, departure.time
                ).isoformat(),
                ATTR_SCHEDULED_AT: datetime.combine(
                    departure.date, departure.time
                ).isoformat(),
                ATTR_REAL_TIME_AT: datetime.combine(
                    departure.rtDate or departure.date,
                    departure.rtTime or departure.time,
                ).isoformat(),
                ATTR_TRACK: departure.rtTrack or departure.track,
            }
            parsed_departures.append(parsed_departure)
        return parsed_departures

    @staticmethod
    def due_in(time: Time, date: Date) -> int:
        """Calculate the due in time in minutes."""
        tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
        now = datetime.now(tz)
        departure_time = datetime.combine(date, time).replace(tzinfo=tz)
        due_in_seconds = (departure_time - now).total_seconds()
        return round(due_in_seconds / 60) if due_in_seconds > 0 else 0


class RejseplanenDiagnosticSensor(SensorEntity):
    """Implementation of Rejseplanen diagnostic sensor."""

    _attr_attribution = "Data provided by rejseplanen.dk"
    _attr_icon = "mdi:information-outline"
    _attr_name = "Rejseplanen Updater Status"
    _attr_unique_id = "rejseplanen_updater_status"
    _attr_entity_category = const.EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: RejseplanenDataUpdateCoordinator, entry_id: str
    ) -> None:
        """Initialize the diagnostic sensor."""
        self.coordinator = coordinator
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        self._attr_device_info = _service_device_info(entry_id)

        self._attr_available = False
        self._attr_extra_state_attributes = self.coordinator.diagnostics_attributes

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added to hass."""
        await super().async_added_to_hass()
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Callback triggered when the coordinator updates data.

        This method is registered with the update coordinator and called whenever
        new data is fetched for the configured stop. It ensures the entity state
        is updated in Home Assistant after each coordinator refresh.
        """
        _LOGGER.debug(
            "Coordinator update callback triggered for sensor %s", self._attr_unique_id
        )
        if (
            not self.coordinator.last_update_success_time
            and not self.coordinator.update_interval
        ):
            self._attr_available = False
            self._attr_native_value = "offline"
            self._attr_extra_state_attributes = {}
            self.async_write_ha_state()
            return

        is_available = self.coordinator.last_update_success_time is not None and (
            self.coordinator.update_interval is None
            or (
                self.coordinator.last_update_success_time
                + self.coordinator.update_interval
                >= dt_util.utcnow()
            )
        )
        self._attr_available = is_available

        self._attr_native_value = "online" if is_available else "offline"
        self._attr_extra_state_attributes = self.coordinator.diagnostics_attributes
        self.async_write_ha_state()
