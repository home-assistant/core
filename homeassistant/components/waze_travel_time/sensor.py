"""Support for Waze travel time sensor."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pywaze.route_calculator import WazeRouteCalculator, WRCError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_REGION,
    EVENT_HOMEASSISTANT_STARTED,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.location import find_coordinates
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_NAME,
    DOMAIN,
    IMPERIAL_UNITS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Waze travel time sensor entry."""
    destination = config_entry.data[CONF_DESTINATION]
    origin = config_entry.data[CONF_ORIGIN]
    region = config_entry.data[CONF_REGION]
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)

    data = WazeTravelTimeData(
        region,
        config_entry,
    )

    sensor = WazeTravelTime(config_entry.entry_id, name, origin, destination, data)

    async_add_entities([sensor], False)


class WazeTravelTime(SensorEntity):
    """Representation of a Waze travel time sensor."""

    _attr_attribution = "Powered by Waze"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_info = DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        name="Waze",
        identifiers={(DOMAIN, DOMAIN)},
        configuration_url="https://www.waze.com",
    )

    def __init__(
        self,
        unique_id: str,
        name: str,
        origin: str,
        destination: str,
        waze_data: WazeTravelTimeData,
    ) -> None:
        """Initialize the Waze travel time sensor."""
        self._attr_unique_id = unique_id
        self._waze_data = waze_data
        self._attr_name = name
        self._origin = origin
        self._destination = destination
        self._attr_icon = "mdi:car"
        self._state = None

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self.first_update
            )
        else:
            await self.first_update()

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self._waze_data.duration is not None:
            return round(self._waze_data.duration)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the last update."""
        if self._waze_data.duration is None:
            return None

        return {
            "duration": self._waze_data.duration,
            "distance": self._waze_data.distance,
            "route": self._waze_data.route,
            "origin": self._waze_data.origin,
            "destination": self._waze_data.destination,
        }

    async def first_update(self, _=None) -> None:
        """Run first update and write state."""
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Fetching Route for %s", self._attr_name)
        self._waze_data.origin = find_coordinates(self.hass, self._origin)
        self._waze_data.destination = find_coordinates(self.hass, self._destination)
        await self._waze_data.async_update()


class WazeTravelTimeData:
    """WazeTravelTime Data object."""

    def __init__(self, region: str, config_entry: ConfigEntry) -> None:
        """Set up WazeRouteCalculator."""
        self.config_entry = config_entry
        self.client: WazeRouteCalculator = WazeRouteCalculator(region)
        self.origin: str | None = None
        self.destination: str | None = None
        self.duration = None
        self.distance = None
        self.route = None

    async def async_update(self):
        """Update WazeRouteCalculator Sensor."""
        _LOGGER.debug(
            "Getting update for origin: %s destination: %s",
            self.origin,
            self.destination,
        )
        if self.origin is not None and self.destination is not None:
            # Grab options on every update
            incl_filter = self.config_entry.options.get(CONF_INCL_FILTER)
            excl_filter = self.config_entry.options.get(CONF_EXCL_FILTER)
            realtime = self.config_entry.options[CONF_REALTIME]
            vehicle_type = self.config_entry.options[CONF_VEHICLE_TYPE]
            vehicle_type = "" if vehicle_type.upper() == "CAR" else vehicle_type.upper()
            avoid_toll_roads = self.config_entry.options[CONF_AVOID_TOLL_ROADS]
            avoid_subscription_roads = self.config_entry.options[
                CONF_AVOID_SUBSCRIPTION_ROADS
            ]
            avoid_ferries = self.config_entry.options[CONF_AVOID_FERRIES]
            units = self.config_entry.options[CONF_UNITS]

            routes = {}
            try:
                routes = await self.client.calc_all_routes_info(
                    self.origin,
                    self.destination,
                    vehicle_type=vehicle_type,
                    avoid_toll_roads=avoid_toll_roads,
                    avoid_subscription_roads=avoid_subscription_roads,
                    avoid_ferries=avoid_ferries,
                    real_time=realtime,
                )

                if incl_filter not in {None, ""}:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if incl_filter.lower() in k.lower()
                    }

                if excl_filter not in {None, ""}:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if excl_filter.lower() not in k.lower()
                    }

                if routes:
                    route = list(routes)[0]
                else:
                    _LOGGER.warning("No routes found")
                    return

                self.duration, distance = routes[route]

                if units == IMPERIAL_UNITS:
                    # Convert to miles.
                    self.distance = DistanceConverter.convert(
                        distance, UnitOfLength.KILOMETERS, UnitOfLength.MILES
                    )
                else:
                    self.distance = distance

                self.route = route
            except WRCError as exp:
                _LOGGER.warning("Error on retrieving data: %s", exp)
                return
            except KeyError:
                _LOGGER.error("Error retrieving data from server")
                return
