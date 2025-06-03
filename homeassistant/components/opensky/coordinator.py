"""DataUpdateCoordinator for the OpenSky integration."""

from __future__ import annotations

from datetime import timedelta

from python_opensky import OpenSky, OpenSkyError, StateVector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_ALTITUDE,
    ATTR_CALLSIGN,
    ATTR_ICAO24,
    ATTR_SENSOR,
    CONF_ALTITUDE,
    DEFAULT_ALTITUDE,
    DOMAIN,
    EVENT_OPENSKY_ENTRY,
    EVENT_OPENSKY_EXIT,
    LOGGER,
)


class OpenSkyDataUpdateCoordinator(DataUpdateCoordinator[int]):
    """An OpenSky Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, opensky: OpenSky
    ) -> None:
        """Initialize the OpenSky data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval={
                True: timedelta(seconds=90),
                False: timedelta(minutes=15),
            }.get(opensky.is_authenticated),
        )
        self._opensky = opensky
        self._previously_tracked: set[str] | None = None
        self._bounding_box = OpenSky.get_bounding_box(
            config_entry.data[CONF_LATITUDE],
            config_entry.data[CONF_LONGITUDE],
            config_entry.options[CONF_RADIUS],
        )
        self._altitude = config_entry.options.get(CONF_ALTITUDE, DEFAULT_ALTITUDE)

    async def _async_update_data(self) -> int:
        try:
            response = await self._opensky.get_states(bounding_box=self._bounding_box)
        except OpenSkyError as exc:
            raise UpdateFailed from exc
        currently_tracked = set()
        flight_metadata: dict[str, StateVector] = {}
        for flight in response.states:
            if not flight.callsign:
                continue
            callsign = flight.callsign.strip()
            if callsign:
                flight_metadata[callsign] = flight
            else:
                continue
            if (
                flight.longitude is None
                or flight.latitude is None
                or flight.on_ground
                or flight.barometric_altitude is None
            ):
                continue
            altitude = flight.barometric_altitude
            if altitude > self._altitude and self._altitude != 0:
                continue
            currently_tracked.add(callsign)
        if self._previously_tracked is not None:
            entries = currently_tracked - self._previously_tracked
            exits = self._previously_tracked - currently_tracked
            self._handle_boundary(entries, EVENT_OPENSKY_ENTRY, flight_metadata)
            self._handle_boundary(exits, EVENT_OPENSKY_EXIT, flight_metadata)
        self._previously_tracked = currently_tracked

        return len(currently_tracked)

    def _handle_boundary(
        self, flights: set[str], event: str, metadata: dict[str, StateVector]
    ) -> None:
        """Handle flights crossing region boundary."""
        for flight in flights:
            if flight in metadata:
                altitude = metadata[flight].barometric_altitude
                longitude = metadata[flight].longitude
                latitude = metadata[flight].latitude
                icao24 = metadata[flight].icao24
            else:
                # Assume Flight has landed if missing.
                altitude = 0
                longitude = None
                latitude = None
                icao24 = None

            data = {
                ATTR_CALLSIGN: flight,
                ATTR_ALTITUDE: altitude,
                ATTR_SENSOR: self.config_entry.title,
                ATTR_LONGITUDE: longitude,
                ATTR_LATITUDE: latitude,
                ATTR_ICAO24: icao24,
            }
            self.hass.bus.fire(event, data)
