"""Support for Google travel time sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import requests

from googlemaps import Client
from googlemaps.distance_matrix import distance_matrix
from googlemaps.exceptions import ApiError, Timeout, TransportError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_LANGUAGE,
    EVENT_HOMEASSISTANT_STARTED,
    UnitOfTime,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.location import find_coordinates
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_USE_ROUTES_API,
    CONF_UNITS,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


def convert_time_to_utc(timestr):
    """Take a string like 08:00:00 and convert it to a unix timestamp."""
    combined = datetime.combine(
        dt_util.start_of_local_day(), dt_util.parse_time(timestr)
    )
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return dt_util.as_timestamp(combined)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Google travel time sensor entry."""
    api_key = config_entry.data[CONF_API_KEY]
    origin = config_entry.data[CONF_ORIGIN]
    destination = config_entry.data[CONF_DESTINATION]
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    use_routes_api = config_entry.options.get(CONF_USE_ROUTES_API, False)

    client = Client(api_key, timeout=10)

    sensor = GoogleTravelTimeSensor(
        config_entry, name, api_key, origin, destination, use_routes_api, client
    )

    async_add_entities([sensor], False)


class GoogleTravelTimeSensor(SensorEntity):
    """Representation of a Google travel time sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, config_entry, name, api_key, origin, destination, use_routes_api, client):
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, api_key)},
            name=DOMAIN,
        )

        self._config_entry = config_entry
        self._matrix = None
        self._api_key = api_key
        self._client = client
        self._origin = origin
        self._destination = destination
        self._use_routes_api = use_routes_api
        self._resolved_origin = None
        self._resolved_destination = None
        self._name = name
        self._state = None

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state is not CoreState.running:
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
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._matrix is None:
            return None

        res = self._matrix.copy()
        options = self._config_entry.options.copy()
        res.update(options)

        if "rows" in res:
            del res["rows"]
        
        if "rows" in self._matrix and self._matrix["rows"]:
            elements = self._matrix["rows"][0].get("elements", [{}])[0]
            res["duration_in_traffic"] = elements.get("duration_in_traffic", {}).get("text", "N/A")
            res["duration"] = elements.get("duration", {}).get("text", "N/A")
            res["distance"] = elements.get("distance", {}).get("text", "N/A")

        res["origin"] = self._resolved_origin
        res["destination"] = self._resolved_destination
        return res

    async def first_update(self, _=None):
        """Run the first update and write the state."""
        await self.hass.async_add_executor_job(self.update)
        self.async_write_ha_state()

    def update(self) -> None:
        """Get the latest data from Google."""
        options_copy = self._config_entry.options.copy()
        dtime = options_copy.get(CONF_DEPARTURE_TIME)
        atime = options_copy.get(CONF_ARRIVAL_TIME)
        if dtime is not None and ":" in dtime:
            options_copy[CONF_DEPARTURE_TIME] = convert_time_to_utc(dtime)
        elif dtime is not None:
            options_copy[CONF_DEPARTURE_TIME] = dtime
        elif atime is None:
            options_copy[CONF_DEPARTURE_TIME] = "now"

        if atime is not None and ":" in atime:
            options_copy[CONF_ARRIVAL_TIME] = convert_time_to_utc(atime)
        elif atime is not None:
            options_copy[CONF_ARRIVAL_TIME] = atime

        self._resolved_origin = find_coordinates(self.hass, self._origin)
        self._resolved_destination = find_coordinates(self.hass, self._destination)

        _LOGGER.debug(
            "Getting update for origin: %s destination: %s",
            self._resolved_origin,
            self._resolved_destination,
        )
        if self._resolved_destination is not None and self._resolved_origin is not None:
            try:
                if options_copy.get("use_routes_api"):
                    # Gebruik de Routes API
                    _LOGGER.debug("Using Routes API for travel time.")
                    self._matrix = self.get_routes_data(options_copy)
                    self._state = self._matrix.get("duration")
                else:
                    # Gebruik de Distance Matrix API
                    _LOGGER.debug("Using Distance Matrix API for travel time.")
                    self._matrix = distance_matrix(
                        self._client,
                        self._resolved_origin,
                        self._resolved_destination,
                        **{k: v for k, v in options_copy.items() if k not in ["use_routes_api"]},
                    )
            except (ApiError, TransportError, Timeout) as ex:
                _LOGGER.error("Error getting travel time: %s", ex)
                self._matrix = None

    # Detecteren of de gebruiker een Place ID of coördinaten gebruikt
    def parse_location(self, location):
        if "," in location:  # Controleer of het een coördinatenpaar is
            lat, lng = map(float, location.split(","))
            return {"latLng": {"latitude": lat, "longitude": lng}}
        else:
            return {"placeId": location}

    def get_routes_data(self, options):
        """Fetch new state data for the sensor."""
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"
        }

        payload = {
            "origin": {"location": self.parse_location(self._resolved_origin)},
            "destination": {"location": self.parse_location(self._resolved_destination)},
            "travelMode": "DRIVE", #options.get("mode", "driving"),
            "languageCode": "en-US",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "units": "METRIC",
            "routeModifiers": {
                "avoidTolls": False,
                "avoidHighways": False,
                "avoidFerries": False
            },
            
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract travel time and distance
            if "routes" in data and data["routes"]:
                route = data["routes"][0]
                duration = int(route["duration"][:-1]) if "duration" in route else 0 # Duration in seconds
                distance = int(route["distanceMeters"]) if "distanceMeters" in route else 0  # Distance in meters

                return {
                    "duration": round(duration / 60),  # Convert to minutes
                    "distance": distance / 1000,  # Convert to kilometers
                    "origin": self._origin,
                    "destination": self._destination,
                }
            else:
                _LOGGER.error("No routes found in the response")
                return None

        except requests.exceptions.RequestException as error:
            _LOGGER.error("Error fetching data from Google Routes API: %s, Payload: %s", error, payload)
            return None
