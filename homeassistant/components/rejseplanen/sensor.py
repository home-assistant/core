"""Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date as Date, datetime, time as Time
import logging
from typing import Any
import zoneinfo

from py_rejseplan.dataclasses.departure import Departure

from homeassistant.components.sensor import SensorEntity, cast
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType, StateType
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
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import RejseplanenDataUpdateCoordinator
from .entity import RejseplanenUpdaterStatusSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rejseplanen transport sensor."""

    _LOGGER.info(
        "Setting up Rejseplanen transport sensor for entry: %s", config_entry.entry_id
    )

    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: RejseplanenDataUpdateCoordinator = entry_data["coordinator"]

    # Only add the updater status sensor for the main entry
    if config_entry.data.get("is_main_entry"):
        async_add_entities(
            [RejseplanenUpdaterStatusSensor(coordinator, config_entry.entry_id)]
        )

    for subentry_id, subentry in config_entry.subentries.items():
        _LOGGER.debug("Subentry %s with data: %s", subentry_id, subentry.data)
        if subentry_id != DOMAIN:
            _LOGGER.warning(
                "Unexpected subentry %s found in Rejseplanen config entry",
                subentry_id,
            )

        entry_data = hass.data[DOMAIN][config_entry.entry_id]
        coordinator = entry_data["coordinator"]

        config = subentry.data
        name = config.get(CONF_NAME, DEFAULT_NAME)
        stop_id = int(config[CONF_STOP_ID])
        route = config.get(CONF_ROUTE, [])
        direction = config.get(CONF_DIRECTION, [])
        departure_type = config.get(CONF_DEPARTURE_TYPE, [])

        async_add_entities(
            [
                RejseplanenTransportSensor(
                    coordinator=coordinator,
                    entry_id=config_entry.entry_id,
                    stop_id=stop_id,
                    name=name,
                    route=route,
                    direction=direction,
                    departure_type=departure_type,
                )
            ],
            config_subentry_id=subentry_id,
        )


class RejseplanenTransportSensor(CoordinatorEntity, SensorEntity):
    """Implementation of Rejseplanen transport sensor."""

    _attr_attribution = "Data provided by rejseplanen.dk"
    _attr_icon = "mdi:bus"

    def __init__(
        self, coordinator, entry_id, stop_id, route, direction, departure_type, name
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._stop_id = stop_id
        self._route = route
        self._direction = direction
        self._departure_type = departure_type
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        cast(RejseplanenDataUpdateCoordinator, self.coordinator).add_stop_id(stop_id)

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
        # other_departures = departures[1:]

        return attributes

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return UnitOfTime.MINUTES

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal of the sensor from Home Assistant."""
        _LOGGER.debug("Removing sensor %s from coordinator", self._attr_unique_id)
        coordinator = cast(RejseplanenDataUpdateCoordinator, self.coordinator)
        coordinator.remove_stop_id(self._stop_id)

    def _get_filtered_departures(self) -> list[dict[str, Any]]:
        """Get filtered departures based on the configured parameters."""
        coordinator = cast(RejseplanenDataUpdateCoordinator, self.coordinator)
        route_filter = self._route if self._route else None
        direction_filter = self._direction if self._direction else None
        departure_type_filter = self._departure_type if self._departure_type else None

        return coordinator.get_filtered_departures(
            stop_id=self._stop_id,
            route_filter=route_filter,
            direction_filter=direction_filter,
            departure_type_filter=departure_type_filter,
        )

    @staticmethod
    def due_in(time: Time, date: Date) -> int:
        """Calculate the due in time in minutes."""
        tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
        now = datetime.now(tz)
        departure_time = datetime.combine(date, time).replace(tzinfo=tz)
        due_in_seconds = (departure_time - now).total_seconds()
        return round(due_in_seconds / 60) if due_in_seconds > 0 else 0
