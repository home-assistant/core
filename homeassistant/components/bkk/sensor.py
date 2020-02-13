"""BKK Futar integration to monitor public transport stops of Budapest city."""

from datetime import datetime, timedelta
import logging

import futar
import voluptuous as vol

from homeassistant.components import group
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import EVENT_HOMEASSISTANT_START, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DOMAIN = "bkk"
CONF_STOP = "stop"
CONF_GROUPED = "grouped"
CONF_ONLY_DEPARTURES = "only_departures"
CONF_MINUTES_AFTER = "minutes_after"
MAX_DEPARTURES = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP): cv.string,
        vol.Optional(CONF_GROUPED, default=False): cv.boolean,
        vol.Optional(CONF_ONLY_DEPARTURES, default=True): cv.boolean,
        vol.Optional(CONF_MINUTES_AFTER, default=120): cv.positive_int,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)

ICONS = {
    "BUS": "mdi:bus",
    "TRAM": "mdi:tram-side",
    "RAIL": "mdi:tram",
    "SUBWAY": "mdi:subway",
    "API": "mdi:api",
}

_LOGGER = logging.getLogger(__name__)


async def async_create_group(hass, name, entities):
    """Create group for bkk route entities."""
    await group.Group.async_create_group(hass, name, entities, user_defined=True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up bkk platform."""
    data_updater = BkkDataUpdater(config)
    try:
        data_updater.get_data()
    except ConnectionError:
        return
    else:
        if data_updater.state == "NOT_FOUND":
            _LOGGER.error(
                "Stop id could not be found. Please specify an existing BKK stop id."
            )
            return
        entities = []
        stop_type = data_updater.data["references"]["stops"][data_updater.stop_id][
            "type"
        ]
        for i in range(MAX_DEPARTURES):
            route = BkkRoute(data_updater.stop_id, i, stop_type)
            entities.append(route)
        data_updater.routes = entities
        async_add_entities(entities, True)
        async_add_entities([data_updater], True)

        async def async_remove_unavailable_entities(event):
            reg = await entity_registry.async_get_registry(hass)
            entities = reg.entities.copy()
            for ent in entities:
                registry_entry = reg.async_get(ent)
                if registry_entry.platform == DOMAIN:
                    entity_id = registry_entry.entity_id
                    state = hass.states.get(entity_id).state
                    if state == STATE_UNAVAILABLE:
                        reg.async_remove(entity_id)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_remove_unavailable_entities
        )
        return True


class BkkDataUpdater(Entity):
    """Data updater class to query api and update entity data."""

    def __init__(self, config):
        """Initialize the sensor."""
        self._name = "BKK Data Updater"
        self.api = futar.BkkFutar()
        self.routes = None
        self.stop_id = (
            f"BKK_{config[CONF_STOP][1:]}"
            if config[CONF_STOP][0] == "#"
            else f"BKK_{config[CONF_STOP]}"
        )
        self._data = None
        self._state = None
        self._icon = ICONS["API"]
        self.is_grouped = config[CONF_GROUPED]
        self._only_departures = config[CONF_ONLY_DEPARTURES]
        self._minutes_after = config[CONF_MINUTES_AFTER]

    def get_data(self):
        """Fetch data from BKK api."""
        try:
            response = self.api.arrivals_and_departures_for_stop(
                stopid=self.stop_id,
                only_departures=self._only_departures,
                minutes_after=self._minutes_after,
            )
        except ConnectionError:
            _LOGGER.error("Unable to fetch data from api.")
        else:
            status = response["status"]
            if status == "OK":
                self._data = response["data"]
            self._state = status
            return self._data

    async def async_added_to_hass(self) -> None:
        """Create group after entity added."""
        entity_ids = [ent.entity_id for ent in self.routes]
        stop_name = self.data["references"]["stops"][self.stop_id]["name"]
        if self.is_grouped:
            await async_create_group(self.hass, stop_name, entity_ids)

    @property
    def state(self):
        """Get BKKDataUpdater state."""
        return self._state

    @property
    def hidden(self) -> bool:
        """Set BKKDataUpdater hidden."""
        return True

    @property
    def name(self):
        """Get BKKDataUpdater name."""
        return self._name

    @property
    def icon(self):
        """Return BBKKDataUpdater icon."""
        return self._icon

    def update(self):
        """Fetch data and update BKKRoute entities."""
        try:
            self.get_data()
        except ConnectionError:
            _LOGGER.error("Unable to fetch data from BKK api!")
        else:
            stop_times = self._data["entry"]["stopTimes"]
            for i, route in enumerate(self.routes):
                try:
                    stop_time = stop_times[i]
                    route.update_fields(
                        stop_time,
                        self._data["references"]["routes"],
                        self._data["references"]["trips"],
                    )
                except IndexError:
                    route.clear_fields()

    @property
    def data(self):
        """Return last fetched data."""
        return self._data


class BkkRoute(Entity):
    """Class representing a route in a stop/station."""

    def __init__(self, stop_id, idx, vehicle_type):
        """Initialize the sensor."""
        self._id = self._line = ""
        self._name = None
        self._entity_idx = idx
        self._stop_id = stop_id
        self._departure_time = 0
        self._predicted_departure_time = 0
        self._route_id = ""
        if vehicle_type in ICONS:
            self._icon = ICONS[vehicle_type]
        else:
            self._icon = "mdi:bus-alert"
        self._attributes = {
            "vehicle": vehicle_type,
            "line": self._line,
            "route_id": self._route_id,
        }
        self._state = None

    def clear_fields(self):
        """Clear BKKRoute entity fields."""
        self._name = "N/A"
        self._departure_time = 0
        self._predicted_departure_time = 0
        self._attributes["wheelchair_accessible"] = ""
        self._attributes["destination"] = ""
        self._state = None

    def update_fields(self, current_stop_time, routes, trips):
        """Update BKKRouter entity fields with fresh data."""
        self._departure_time = (
            current_stop_time["departureTime"]
            if "departureTime" in current_stop_time
            else 0
        )
        self._predicted_departure_time = (
            current_stop_time["predictedDepartureTime"]
            if "predictedDepartureTime" in current_stop_time
            else 0
        )
        self._line = routes[trips[current_stop_time["tripId"]]["routeId"]]["shortName"]
        self._id = routes[trips[current_stop_time["tripId"]]["routeId"]]["id"]
        self._name = (
            f"{self.line}->{trips[current_stop_time['tripId']]['tripHeadsign']}"
        )
        self._attributes["line"] = self._line
        self._attributes["route_id"] = self._id
        self._attributes["wheelchair_accessible"] = trips[current_stop_time["tripId"]][
            "wheelchairAccessible"
        ]
        self._attributes["destination"] = trips[current_stop_time["tripId"]][
            "tripHeadsign"
        ]
        self.calculate_state()

    @property
    def icon(self):
        """Return entity icon."""
        return self._icon

    @property
    def state(self):
        """Return route state."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return measurement unit."""
        return "min"

    @property
    def unique_id(self):
        """Return unique id."""
        return f"{self._stop_id}_{self._entity_idx}"

    def update(self):
        """Update entity state."""
        pass

    @staticmethod
    def to_iso_datetime(epoch):
        """Convert epoch date format to ISO format."""
        if epoch:
            return datetime.isoformat(datetime.fromtimestamp(epoch))
        return None

    @staticmethod
    def calc_state_value(now, p_time):
        """Return time between now and a timestamp in minutes."""
        return int((datetime.fromtimestamp(p_time) - now).total_seconds() / 60)

    def calculate_state(self):
        """Calculate entity state, return value in minutes."""
        now = datetime.now()
        state = None
        t_next = datetime.fromtimestamp(self._departure_time)
        t_predicted = datetime.fromtimestamp(self._predicted_departure_time)
        if t_next > now < t_predicted:
            predicted = self.calc_state_value(now, self._predicted_departure_time)
            next_time = self.calc_state_value(now, self._departure_time)
            state = min(next_time, predicted)
        elif t_next < now < t_predicted:
            state = self.calc_state_value(now, self._predicted_departure_time)
        elif t_next > now > t_predicted:
            state = self.calc_state_value(now, self._departure_time)
        if state:
            self._attributes.update(
                {
                    "departure_time": self.to_iso_datetime(self._departure_time),
                    "predicted_departure_time": self.to_iso_datetime(
                        self._predicted_departure_time
                    ),
                }
            )
            self._state = state
        return state

    @property
    def line(self):
        """Return route/line."""
        return self._line
