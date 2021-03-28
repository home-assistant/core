"""Support for Google travel time sensors."""
from datetime import datetime, timedelta
import logging
from typing import Callable, List

import googlemaps
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_OPTIONS,
    CONF_ORIGIN,
    CONF_TRAVEL_MODE,
    DEFAULT_NAME,
    DOMAIN,
    GOOGLE_IMPORT_SCHEMA,
    GOOGLE_OPTIONS_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        **GOOGLE_IMPORT_SCHEMA,
        vol.Optional(CONF_OPTIONS, default={CONF_MODE: "driving"}): vol.All(
            dict,
            vol.Schema(GOOGLE_OPTIONS_SCHEMA),
        ),
    }
)

TRACKABLE_DOMAINS = ["device_tracker", "sensor", "zone", "person"]
DATA_KEY = "google_travel_time"


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
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up a Google travel time sensor entry."""

    def run_setup(event):
        """
        Delay the setup until Home Assistant is fully initialized.

        This allows any entities to be created already
        """
        hass.data.setdefault(DATA_KEY, [])
        options = config_entry.data.get(CONF_OPTIONS)

        if options.get("units") is None:
            options["units"] = hass.config.units.name

        travel_mode = config_entry.data.get(CONF_TRAVEL_MODE)
        mode = options.get(CONF_MODE)

        if travel_mode is not None:
            wstr = (
                "Google Travel Time: travel_mode is deprecated, please "
                "add mode to the options dictionary instead!"
            )
            _LOGGER.warning(wstr)
            if mode is None:
                options[CONF_MODE] = travel_mode

        api_key = config_entry.data.get(CONF_API_KEY)
        origin = config_entry.data.get(CONF_ORIGIN)
        destination = config_entry.data.get(CONF_DESTINATION)
        name = config_entry.data.get(
            CONF_NAME, f"{DEFAULT_NAME}: {origin} -> {destination}"
        )

        sensor = GoogleTravelTimeSensor(
            hass, config_entry.unique_id, name, api_key, origin, destination, options
        )
        hass.data[DATA_KEY].append(sensor)

        if sensor.valid_api_connection:
            async_add_entities([sensor], True)

    # Wait until start event is sent to load this component.
    await hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, run_setup)


async def async_setup_platform(
    hass, config, add_entities_callback, discovery_info=None
):
    """Set up the Google travel time platform."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    _LOGGER.info(
        "Your Google travel time configuration has been imported into the UI; "
        "please remove it from configuration.yaml as support for it will be "
        "removed in a future release."
    )

    return True


class GoogleTravelTimeSensor(SensorEntity):
    """Representation of a Google travel time sensor."""

    def __init__(self, hass, unique_id, name, api_key, origin, destination, options):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._options = options
        self._unit_of_measurement = TIME_MINUTES
        self._matrix = None
        self._api_key = api_key
        self._unique_id = unique_id
        self.valid_api_connection = True

        # Check if location is a trackable entity
        if origin.split(".", 1)[0] in TRACKABLE_DOMAINS:
            self._origin_entity_id = origin
        else:
            self._origin = origin

        if destination.split(".", 1)[0] in TRACKABLE_DOMAINS:
            self._destination_entity_id = destination
        else:
            self._destination = destination

        self._client = googlemaps.Client(api_key, timeout=10)
        try:
            self.update()
        except googlemaps.exceptions.ApiError as exp:
            _LOGGER.error(exp)
            self.valid_api_connection = False
            return

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._matrix is None:
            return None

        _data = self._matrix["rows"][0]["elements"][0]
        if "duration_in_traffic" in _data:
            return round(_data["duration_in_traffic"]["value"] / 60)
        if "duration" in _data:
            return round(_data["duration"]["value"] / 60)
        return None

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": DOMAIN,
            "identifiers": {(DOMAIN, self._api_key)},
            "entry_type": "service",
        }

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._matrix is None:
            return None

        res = self._matrix.copy()
        res.update(self._options)
        del res["rows"]
        _data = self._matrix["rows"][0]["elements"][0]
        if "duration_in_traffic" in _data:
            res["duration_in_traffic"] = _data["duration_in_traffic"]["text"]
        if "duration" in _data:
            res["duration"] = _data["duration"]["text"]
        if "distance" in _data:
            res["distance"] = _data["distance"]["text"]
        res["origin"] = self._origin
        res["destination"] = self._destination
        res[ATTR_ATTRIBUTION] = ATTRIBUTION
        return res

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from Google."""
        options_copy = self._options.copy()
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

        # Convert device_trackers to google friendly location
        if hasattr(self, "_origin_entity_id"):
            self._origin = self._get_location_from_entity(self._origin_entity_id)

        if hasattr(self, "_destination_entity_id"):
            self._destination = self._get_location_from_entity(
                self._destination_entity_id
            )

        self._destination = self._resolve_zone(self._destination)
        self._origin = self._resolve_zone(self._origin)

        if self._destination is not None and self._origin is not None:
            self._matrix = self._client.distance_matrix(
                self._origin, self._destination, **options_copy
            )

    def _get_location_from_entity(self, entity_id):
        """Get the location from the entity state or attributes."""
        entity = self._hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            self.valid_api_connection = False
            return None

        # Check if the entity has location attributes
        if location.has_location(entity):
            return self._get_location_from_attributes(entity)

        # Check if device is in a zone
        zone_entity = self._hass.states.get("zone.%s" % entity.state)
        if location.has_location(zone_entity):
            _LOGGER.debug(
                "%s is in %s, getting zone location", entity_id, zone_entity.entity_id
            )
            return self._get_location_from_attributes(zone_entity)

        # If zone was not found in state then use the state as the location
        if entity_id.startswith("sensor."):
            return entity.state

        # When everything fails just return nothing
        return None

    @staticmethod
    def _get_location_from_attributes(entity):
        """Get the lat/long string from an entities attributes."""
        attr = entity.attributes
        return f"{attr.get(ATTR_LATITUDE)},{attr.get(ATTR_LONGITUDE)}"

    def _resolve_zone(self, friendly_name):
        entities = self._hass.states.all()
        for entity in entities:
            if entity.domain == "zone" and entity.name == friendly_name:
                return self._get_location_from_attributes(entity)

        return friendly_name
