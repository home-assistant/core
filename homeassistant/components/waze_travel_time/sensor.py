"""Support for Waze travel time sensor."""
from __future__ import annotations

from datetime import timedelta
import logging
import re
from typing import Any, Callable

import WazeRouteCalculator
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_REGION,
    CONF_UNIT_SYSTEM_IMPERIAL,
    EVENT_HOMEASSISTANT_START,
    TIME_MINUTES,
)
from homeassistant.core import Config, CoreState, HomeAssistant
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_DESTINATION,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_ORIGIN,
    ATTR_ROUTE,
    ATTRIBUTION,
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
    DEFAULT_AVOID_FERRIES,
    DEFAULT_AVOID_SUBSCRIPTION_ROADS,
    DEFAULT_AVOID_TOLL_ROADS,
    DEFAULT_NAME,
    DEFAULT_REALTIME,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
    ICON,
    REGIONS,
    UNITS,
    VEHICLE_TYPES,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ORIGIN): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_REGION): vol.In(REGIONS),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_INCL_FILTER): cv.string,
        vol.Optional(CONF_EXCL_FILTER): cv.string,
        vol.Optional(CONF_REALTIME, default=DEFAULT_REALTIME): cv.boolean,
        vol.Optional(CONF_VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE): vol.In(
            VEHICLE_TYPES
        ),
        vol.Optional(CONF_UNITS): vol.In(UNITS),
        vol.Optional(
            CONF_AVOID_TOLL_ROADS, default=DEFAULT_AVOID_TOLL_ROADS
        ): cv.boolean,
        vol.Optional(
            CONF_AVOID_SUBSCRIPTION_ROADS, default=DEFAULT_AVOID_SUBSCRIPTION_ROADS
        ): cv.boolean,
        vol.Optional(CONF_AVOID_FERRIES, default=DEFAULT_AVOID_FERRIES): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant, config: Config, async_add_entities, discovery_info=None
):
    """Set up the Waze travel time sensor platform."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    _LOGGER.warning(
        "Your Waze configuration has been imported into the UI; "
        "please remove it from configuration.yaml as support for it "
        "will be removed in a future release"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[SensorEntity], bool], None],
) -> None:
    """Set up a Waze travel time sensor entry."""
    DEFAULTS = {
        CONF_REALTIME: DEFAULT_REALTIME,
        CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
        CONF_UNITS: hass.config.units.name,
        CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
        CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
        CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
    }
    name = None
    if not config_entry.options:
        new_data = config_entry.data.copy()
        name = new_data.pop(CONF_NAME, None)
        options = {}
        for key in [
            CONF_INCL_FILTER,
            CONF_EXCL_FILTER,
            CONF_REALTIME,
            CONF_VEHICLE_TYPE,
            CONF_AVOID_TOLL_ROADS,
            CONF_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_FERRIES,
            CONF_UNITS,
        ]:
            if key in new_data:
                options[key] = new_data.pop(key)
            elif key in DEFAULTS:
                options[key] = DEFAULTS[key]

        await hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=options
        )

    destination = config_entry.data[CONF_DESTINATION]
    origin = config_entry.data[CONF_ORIGIN]
    region = config_entry.data[CONF_REGION]
    name = name or f"{DEFAULT_NAME}: {origin} -> {destination}"

    incl_filter = config_entry.options.get(CONF_INCL_FILTER)
    excl_filter = config_entry.options.get(CONF_EXCL_FILTER)
    realtime = config_entry.options[CONF_REALTIME]
    vehicle_type = config_entry.options[CONF_VEHICLE_TYPE]
    avoid_toll_roads = config_entry.options[CONF_AVOID_TOLL_ROADS]
    avoid_subscription_roads = config_entry.options[CONF_AVOID_SUBSCRIPTION_ROADS]
    avoid_ferries = config_entry.options[CONF_AVOID_FERRIES]
    units = config_entry.options[CONF_UNITS]

    data = WazeTravelTimeData(
        None,
        None,
        region,
        incl_filter,
        excl_filter,
        realtime,
        units,
        vehicle_type,
        avoid_toll_roads,
        avoid_subscription_roads,
        avoid_ferries,
    )

    sensor = WazeTravelTime(config_entry.unique_id, name, origin, destination, data)

    async_add_entities([sensor], False)


def _get_location_from_attributes(state):
    """Get the lat/long string from an states attributes."""
    attr = state.attributes
    return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))


class WazeTravelTime(SensorEntity):
    """Representation of a Waze travel time sensor."""

    def __init__(self, unique_id, name, origin, destination, waze_data):
        """Initialize the Waze travel time sensor."""
        self._unique_id = unique_id
        self._waze_data = waze_data
        self._name = name
        self._state = None
        self._origin_entity_id = None
        self._destination_entity_id = None

        # Attempt to find entity_id without finding address with period.
        pattern = "(?<![a-zA-Z0-9 ])[a-z_]+[.][a-zA-Z0-9_]+"

        if re.fullmatch(pattern, origin):
            _LOGGER.debug("Found origin source entity %s", origin)
            self._origin_entity_id = origin
        else:
            self._waze_data.origin = origin

        if re.fullmatch(pattern, destination):
            _LOGGER.debug("Found destination source entity %s", destination)
            self._destination_entity_id = destination
        else:
            self._waze_data.destination = destination

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, lambda _: self.update
            )
        else:
            self.hass.async_add_executor_job(self.update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._waze_data.duration is not None:
            return round(self._waze_data.duration)

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TIME_MINUTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        if self._waze_data.duration is None:
            return None

        res = {ATTR_ATTRIBUTION: ATTRIBUTION}
        res[ATTR_DURATION] = self._waze_data.duration
        res[ATTR_DISTANCE] = self._waze_data.distance
        res[ATTR_ROUTE] = self._waze_data.route
        res[ATTR_ORIGIN] = self._waze_data.origin
        res[ATTR_DESTINATION] = self._waze_data.destination
        return res

    def _get_location_from_entity(self, entity_id):
        """Get the location from the entity_id."""
        state = self.hass.states.get(entity_id)

        if state is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            return None

        # Check if the entity has location attributes.
        if location.has_location(state):
            _LOGGER.debug("Getting %s location", entity_id)
            return _get_location_from_attributes(state)

        # Check if device is inside a zone.
        zone_state = self.hass.states.get(f"zone.{state.state}")
        if location.has_location(zone_state):
            _LOGGER.debug(
                "%s is in %s, getting zone location", entity_id, zone_state.entity_id
            )
            return _get_location_from_attributes(zone_state)

        # If zone was not found in state then use the state as the location.
        if entity_id.startswith("sensor."):
            return state.state

        # When everything fails just return nothing.
        return None

    def _resolve_zone(self, friendly_name):
        """Get a lat/long from a zones friendly_name."""
        states = self.hass.states.all()
        for state in states:
            if state.domain == "zone" and state.name == friendly_name:
                return _get_location_from_attributes(state)

        return friendly_name

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Fetching Route for %s", self._name)
        # Get origin latitude and longitude from entity_id.
        if self._origin_entity_id is not None:
            self._waze_data.origin = self._get_location_from_entity(
                self._origin_entity_id
            )

        # Get destination latitude and longitude from entity_id.
        if self._destination_entity_id is not None:
            self._waze_data.destination = self._get_location_from_entity(
                self._destination_entity_id
            )

        # Get origin from zone name.
        self._waze_data.origin = self._resolve_zone(self._waze_data.origin)

        # Get destination from zone name.
        self._waze_data.destination = self._resolve_zone(self._waze_data.destination)

        self._waze_data.update()

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device specific attributes."""
        return {
            "name": "Waze",
            "identifiers": {(DOMAIN, DOMAIN)},
            "entry_type": "service",
        }

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self._unique_id


class WazeTravelTimeData:
    """WazeTravelTime Data object."""

    def __init__(
        self,
        origin,
        destination,
        region,
        include,
        exclude,
        realtime,
        units,
        vehicle_type,
        avoid_toll_roads,
        avoid_subscription_roads,
        avoid_ferries,
    ):
        """Set up WazeRouteCalculator."""

        self._calc = WazeRouteCalculator

        self.origin = origin
        self.destination = destination
        self.region = region
        self.include = include
        self.exclude = exclude
        self.realtime = realtime
        self.units = units
        self.duration = None
        self.distance = None
        self.route = None
        self.avoid_toll_roads = avoid_toll_roads
        self.avoid_subscription_roads = avoid_subscription_roads
        self.avoid_ferries = avoid_ferries

        # Currently WazeRouteCalc only supports PRIVATE, TAXI, MOTORCYCLE.
        if vehicle_type.upper() == "CAR":
            # Empty means PRIVATE for waze which translates to car.
            self.vehicle_type = ""
        else:
            self.vehicle_type = vehicle_type.upper()

    def update(self):
        """Update WazeRouteCalculator Sensor."""
        if self.origin is not None and self.destination is not None:
            try:
                params = self._calc.WazeRouteCalculator(
                    self.origin,
                    self.destination,
                    self.region,
                    self.vehicle_type,
                    self.avoid_toll_roads,
                    self.avoid_subscription_roads,
                    self.avoid_ferries,
                )
                routes = params.calc_all_routes_info(real_time=self.realtime)

                if self.include is not None:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if self.include.lower() in k.lower()
                    }

                if self.exclude is not None:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if self.exclude.lower() not in k.lower()
                    }

                route = list(routes)[0]

                self.duration, distance = routes[route]

                if self.units == CONF_UNIT_SYSTEM_IMPERIAL:
                    # Convert to miles.
                    self.distance = distance / 1.609
                else:
                    self.distance = distance

                self.route = route
            except self._calc.WRCError as exp:
                _LOGGER.warning("Error on retrieving data: %s", exp)
                return
            except KeyError:
                _LOGGER.error("Error retrieving data from server")
                return
