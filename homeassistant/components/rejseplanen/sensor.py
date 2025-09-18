"""Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date as Date, datetime, time as Time, timedelta
import logging
from typing import Any
import zoneinfo

from py_rejseplan.dataclasses.departure import Departure

from homeassistant import const
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
)
from .coordinator import RejseplanenDataUpdateCoordinator
from .entity import RejseplanenUpdaterStatusSensor

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
    coordinator: RejseplanenDataUpdateCoordinator = RejseplanenDataUpdateCoordinator(
        hass,
        config_entry,
    )
    entry_data["coordinator"] = coordinator

    # Only add the updater status sensor for the main entry
    if config_entry.domain == DOMAIN:
        async_add_entities(
            [RejseplanenUpdaterStatusSensor(coordinator, config_entry.entry_id)]
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
        unique_id = subentry.unique_id

        async_add_entities(
            [
                RejseplanenTransportSensor(
                    coordinator=coordinator,
                    stop_id=stop_id,
                    name=name,
                    route=route,
                    direction=direction,
                    departure_type=departure_type,
                    unique_id=unique_id,
                )
            ],
            config_subentry_id=subentry_id,
        )

    await coordinator.async_config_entry_first_refresh()


class RejseplanenTransportSensor(
    CoordinatorEntity[RejseplanenDataUpdateCoordinator], SensorEntity
):
    """Implementation of Rejseplanen transport sensor."""

    _attr_attribution = "Data provided by rejseplanen.dk"
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        coordinator,
        stop_id,
        route,
        direction,
        departure_type,
        name,
        unique_id=None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id
        self._route = route
        self._direction = direction
        self._departure_type = departure_type
        self._attr_name = name
        self.coordinator.add_stop_id(stop_id)
        self._unsub_interval: Callable[[], None] | None = None
        self._attr_unique_id = unique_id
        """Initialize the sensor's state."""
        self._attr_native_value = self.native_value

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        departures: list[Departure] = self._get_filtered_departures()
        if departures:
            next_departure = departures[0]
            next_date = next_departure.rtDate or next_departure.date
            next_time = next_departure.rtTime or next_departure.time
            return self.due_in(date=next_date, time=next_time)
        return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
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

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return const.UnitOfTime.MINUTES

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added to hass."""
        await super().async_added_to_hass()
        self._unsub_interval = async_track_time_interval(
            self.hass,
            self._handle_minute_tick,
            timedelta(minutes=1),
            name=f"rejseplanen_{self._attr_unique_id}_minute_tick",
        )

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
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Coordinator update callback triggered for sensor %s", self._attr_unique_id
        )
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

    def _get_filtered_departures(self) -> list[dict[str, Any]]:
        """Get filtered departures based on the configured parameters."""
        route_filter = self._route if self._route else None
        direction_filter = self._direction if self._direction else None
        departure_type_filter = self._departure_type if self._departure_type else None

        return self.coordinator.get_filtered_departures(
            stop_id=self._stop_id,
            route_filter=route_filter,
            direction_filter=direction_filter,
            departure_type_filter=departure_type_filter,
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
