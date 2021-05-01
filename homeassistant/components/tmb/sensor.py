"""Support for TMB (Transports Metropolitans de Barcelona) Barcelona public transport."""
from datetime import timedelta
import logging

from requests import HTTPError
from tmb import IBus, Planner

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_NAME,
    ATTR_SECONDS,
    CONF_NAME,
    TIME_MINUTES,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    ATTR_BUS_STOP,
    ATTR_DESCRIPTION,
    ATTR_IN_TRANSIT,
    ATTR_LINE,
    ATTR_TRANSFERS,
    ATTR_WAITING,
    ATTR_WALK_DISTANCE,
    ATTRIBUTION,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_BUS_STOP,
    CONF_FROM_LATITUDE,
    CONF_FROM_LONGITUDE,
    CONF_LINE,
    CONF_SERVICE,
    CONF_TO_LATITUDE,
    CONF_TO_LONGITUDE,
    DOMAIN,
    ICON_IBUS,
    ICON_PLANNER,
    SERVICE_IBUS,
    SERVICE_PLANNER,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES_IBUS = timedelta(seconds=60)
MIN_TIME_BETWEEN_UPDATES_PLANNER = timedelta(seconds=300)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi sensor from a config entry."""
    entities = []

    if config_entry.data[CONF_SERVICE] == SERVICE_IBUS:
        ibus_client = IBus(
            hass.data[DOMAIN][CONF_APP_ID], hass.data[DOMAIN][CONF_APP_KEY]
        )
        entities.append(
            TMBIBusSensor(
                ibus_client,
                config_entry.data[CONF_BUS_STOP],
                config_entry.data[CONF_LINE],
                config_entry.data[CONF_NAME],
            )
        )
    elif config_entry.data[CONF_SERVICE] == SERVICE_PLANNER:
        planner_client = Planner(
            hass.data[DOMAIN][CONF_APP_ID], hass.data[DOMAIN][CONF_APP_KEY]
        )
        from_latlon = f"{config_entry.data[CONF_FROM_LATITUDE]},{config_entry.data[CONF_FROM_LONGITUDE]}"
        to_latlon = f"{config_entry.data[CONF_TO_LATITUDE]},{config_entry.data[CONF_TO_LONGITUDE]}"
        name = config_entry.data[CONF_NAME]

        entities.append(TMBPlannerSensor(planner_client, from_latlon, to_latlon, name))

    async_add_entities(entities, update_before_add=True)


class TMBIBusSensor(Entity):
    """Implementation of a TMB line/stop Sensor."""

    def __init__(self, ibus_client, stop, line, name):
        """Initialize the sensor."""
        self._ibus_client = ibus_client
        self._stop = stop
        self._line = line.upper()
        self._name = f"{SERVICE_IBUS}: {name}"
        self._unit = TIME_MINUTES
        self._state = None
        self._service = SERVICE_IBUS

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON_IBUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"{self._service}_{self._stop}_{self._line}_{self._name}"

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BUS_STOP: self._stop,
            ATTR_LINE: self._line,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES_IBUS)
    def update(self):
        """Get the next bus information."""
        try:
            self._state = self._ibus_client.get_stop_forecast(self._stop, self._line)
        except HTTPError:
            _LOGGER.error(
                "Unable to fetch data from TMB API. Please check your API keys are valid"
            )


class TMBPlannerSensor(Entity):
    """Implementation of a TMB line/stop Sensor."""

    def __init__(self, planner_client, from_coords, to_coords, name):
        """Initialize the sensor."""
        self._planner_client = planner_client
        self._from_coords = from_coords
        self._to_coords = to_coords
        self._unit = TIME_MINUTES
        self._name = f"{SERVICE_PLANNER}: {name}"
        self._attr_description = None
        self._attr_duration_in_seconds = None
        self._attr_transit_time = None
        self._attr_waiting_time = None
        self._attr_walk_distance = None
        self._attr_transfers = None
        self._state = None
        self._service = SERVICE_PLANNER

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON_PLANNER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"{self._service}_{self._name}"

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_NAME: self._name,
            ATTR_DESCRIPTION: self._attr_description,
            ATTR_SECONDS: self._attr_duration_in_seconds,
            ATTR_IN_TRANSIT: self._attr_transit_time,
            ATTR_WAITING: self._attr_waiting_time,
            ATTR_WALK_DISTANCE: self._attr_walk_distance,
            ATTR_TRANSFERS: self._attr_transfers,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES_PLANNER)
    def update(self):
        """Get the next bus information."""
        try:
            plan = self._planner_client.get_shortest_itinerary(
                self._from_coords, self._to_coords
            )
            self._state = plan["durationInMinutes"]
            self._attr_description = plan["description"]
            self._attr_duration_in_seconds = plan["durationInSeconds"]
            self._attr_transit_time = plan["transitTime"]
            self._attr_waiting_time = plan["waitingTime"]
            self._attr_walk_distance = plan["walkDistance"]
            self._attr_transfers = plan["transfers"]

        except HTTPError:
            _LOGGER.error(
                "Unable to fetch data from TMB API. Please check your API keys"
            )
