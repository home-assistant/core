"""Support for Waze travel time sensor."""
from __future__ import annotations

from datetime import timedelta
import logging
import re

from WazeRouteCalculator import WazeRouteCalculator, WRCError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_ENTITY_NAMESPACE,
    CONF_NAME,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM_IMPERIAL,
    EVENT_HOMEASSISTANT_STARTED,
    TIME_MINUTES,
)
from homeassistant.core import Config, CoreState, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    ENTITY_ID_PATTERN,
    ICON,
    REGIONS,
    UNITS,
    VEHICLE_TYPES,
)
from .helpers import get_location_from_entity, resolve_zone

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
        # Remove options to exclude from import
        vol.Remove(CONF_ENTITY_NAMESPACE): cv.string,
        vol.Remove(CONF_SCAN_INTERVAL): cv.time_period,
    },
    extra=vol.REMOVE_EXTRA,
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Waze travel time sensor entry."""
    defaults = {
        CONF_REALTIME: DEFAULT_REALTIME,
        CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
        CONF_UNITS: hass.config.units.name,
        CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
        CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
        CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
    }

    if not config_entry.options:
        new_data = config_entry.data.copy()
        options = {}
        for key in (
            CONF_INCL_FILTER,
            CONF_EXCL_FILTER,
            CONF_REALTIME,
            CONF_VEHICLE_TYPE,
            CONF_AVOID_TOLL_ROADS,
            CONF_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_FERRIES,
            CONF_UNITS,
        ):
            if key in new_data:
                options[key] = new_data.pop(key)
            elif key in defaults:
                options[key] = defaults[key]

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=options
        )

    destination = config_entry.data[CONF_DESTINATION]
    origin = config_entry.data[CONF_ORIGIN]
    region = config_entry.data[CONF_REGION]
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)

    data = WazeTravelTimeData(
        None,
        None,
        region,
        config_entry,
    )

    sensor = WazeTravelTime(config_entry.entry_id, name, origin, destination, data)

    async_add_entities([sensor], False)


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
        cmpl_re = re.compile(ENTITY_ID_PATTERN)
        if cmpl_re.fullmatch(origin):
            _LOGGER.debug("Found origin source entity %s", origin)
            self._origin_entity_id = origin
        else:
            self._waze_data.origin = origin

        if cmpl_re.fullmatch(destination):
            _LOGGER.debug("Found destination source entity %s", destination)
            self._destination_entity_id = destination
        else:
            self._waze_data.destination = destination

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self.first_update
            )
        else:
            await self.first_update()

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

    async def first_update(self, _=None):
        """Run first update and write state."""
        await self.hass.async_add_executor_job(self.update)
        self.async_write_ha_state()

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Fetching Route for %s", self._name)
        # Get origin latitude and longitude from entity_id.
        if self._origin_entity_id is not None:
            self._waze_data.origin = get_location_from_entity(
                self.hass, _LOGGER, self._origin_entity_id
            )

        # Get destination latitude and longitude from entity_id.
        if self._destination_entity_id is not None:
            self._waze_data.destination = get_location_from_entity(
                self.hass, _LOGGER, self._destination_entity_id
            )

        # Get origin from zone name.
        self._waze_data.origin = resolve_zone(self.hass, self._waze_data.origin)

        # Get destination from zone name.
        self._waze_data.destination = resolve_zone(
            self.hass, self._waze_data.destination
        )

        self._waze_data.update()

    @property
    def device_info(self) -> DeviceInfo:
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

    def __init__(self, origin, destination, region, config_entry):
        """Set up WazeRouteCalculator."""
        self.origin = origin
        self.destination = destination
        self.region = region
        self.config_entry = config_entry
        self.duration = None
        self.distance = None
        self.route = None

    def update(self):
        """Update WazeRouteCalculator Sensor."""
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

            try:
                params = WazeRouteCalculator(
                    self.origin,
                    self.destination,
                    self.region,
                    vehicle_type,
                    avoid_toll_roads,
                    avoid_subscription_roads,
                    avoid_ferries,
                )
                routes = params.calc_all_routes_info(real_time=realtime)

                if incl_filter is not None:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if incl_filter.lower() in k.lower()
                    }

                if excl_filter is not None:
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

                if units == CONF_UNIT_SYSTEM_IMPERIAL:
                    # Convert to miles.
                    self.distance = distance / 1.609
                else:
                    self.distance = distance

                self.route = route
            except WRCError as exp:
                _LOGGER.warning("Error on retrieving data: %s", exp)
                return
            except KeyError:
                _LOGGER.error("Error retrieving data from server")
                return
