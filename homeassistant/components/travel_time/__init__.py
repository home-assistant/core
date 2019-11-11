"""The travel_time integration."""
import voluptuous as vol
from datetime import timedelta
import logging
from typing import Callable, Dict, Optional, Union
from homeassistant.core import HomeAssistant, State

from homeassistant.helpers import location
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MODE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

from .const import DOMAIN

CONF_DESTINATION_LATITUDE = "destination_latitude"
CONF_DESTINATION_LONGITUDE = "destination_longitude"
CONF_DESTINATION_ENTITY_ID = "destination_entity_id"
CONF_ORIGIN_LATITUDE = "origin_latitude"
CONF_ORIGIN_LONGITUDE = "origin_longitude"
CONF_ORIGIN_ENTITY_ID = "origin_entity_id"

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

ICON_BICYCLE = "mdi:bike"
ICON_CAR = "mdi:car"
ICON_PEDESTRIAN = "mdi:walk"
ICON_PUBLIC = "mdi:bus"
ICON_TRUCK = "mdi:truck"

ATTR_DURATION = "duration"
ATTR_DISTANCE = "distance"
ATTR_ROUTE = "route"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"

ATTR_UNIT_SYSTEM = CONF_UNIT_SYSTEM

ATTR_DURATION_IN_TRAFFIC = "duration_in_traffic"
ATTR_ORIGIN_NAME = "origin_name"
ATTR_DESTINATION_NAME = "destination_name"

UNIT_OF_MEASUREMENT = "min"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.All(
            cv.has_at_least_one_key(
                CONF_DESTINATION_LATITUDE, CONF_DESTINATION_ENTITY_ID
            ),
            cv.has_at_least_one_key(CONF_ORIGIN_LATITUDE, CONF_ORIGIN_ENTITY_ID),
            cv.PLATFORM_SCHEMA.extend(
                {
                    vol.Inclusive(
                        CONF_DESTINATION_LATITUDE, "destination_coordinates"
                    ): cv.latitude,
                    vol.Inclusive(
                        CONF_DESTINATION_LONGITUDE, "destination_coordinates"
                    ): cv.longitude,
                    vol.Exclusive(
                        CONF_DESTINATION_LATITUDE, "destination"
                    ): cv.latitude,
                    vol.Exclusive(
                        CONF_DESTINATION_ENTITY_ID, "destination"
                    ): cv.entity_id,
                    vol.Inclusive(
                        CONF_ORIGIN_LATITUDE, "origin_coordinates"
                    ): cv.latitude,
                    vol.Inclusive(
                        CONF_ORIGIN_LONGITUDE, "origin_coordinates"
                    ): cv.longitude,
                    vol.Exclusive(CONF_ORIGIN_LATITUDE, "origin"): cv.latitude,
                    vol.Exclusive(CONF_ORIGIN_ENTITY_ID, "origin"): cv.entity_id,
                    vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
                }
            ),
        ),
    }
)


async def async_setup(hass, config):
    """Set up the travel_time integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for travel_time."""
    return True


@bind_hass
async def get_location_from_entity(
    hass, entity_id: str, recursion_history: Optional[list] = None
) -> Optional[str]:
    """Get the location from the entity state or attributes."""
    entity = hass.states.get(entity_id)

    if entity is None:
        _LOGGER.error("Unable to find entity %s", entity_id)
        return None

    # Check if the entity has location attributes
    if location.has_location(entity):
        return _get_location_from_attributes(entity)

    # Check if device is in a zone
    zone_entity = hass.states.get("zone.{}".format(entity.state))
    if location.has_location(zone_entity):
        _LOGGER.debug(
            "%s is in %s, getting zone location", entity_id, zone_entity.entity_id
        )
        return _get_location_from_attributes(zone_entity)

    # Resolve nested entity
    if recursion_history is None:
        recursion_history = []
    recursion_history.append(entity_id)
    if entity.state in recursion_history:
        _LOGGER.error(
            "Circular Reference detected. The state of %s has already been checked.",
            entity.state,
        )
        return None
    _LOGGER.debug("Getting nested entity for state: %s", entity.state)
    nested_entity = hass.states.get(entity.state)
    if nested_entity is not None:
        _LOGGER.debug("Resolving nested entity_id: %s", entity.state)
        return await _get_location_from_entity(entity.state, recursion_history)

    # Check if state is valid coordinate set
    if _entity_state_is_valid_coordinate_set(entity.state):
        return entity.state

    _LOGGER.error(
        "The state of %s is not a valid set of coordinates: %s",
        entity_id,
        entity.state,
    )
    return None


@staticmethod
def _entity_state_is_valid_coordinate_set(state: str) -> bool:
    """Check that the given string is a valid set of coordinates."""
    schema = vol.Schema(cv.gps)
    try:
        coordinates = state.split(",")
        schema(coordinates)
        return True
    except (vol.MultipleInvalid):
        return False


@staticmethod
def _get_location_from_attributes(entity: State) -> str:
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))


class TravelTimeEntity(Entity):
    """Representation of a travel_time entity."""

    @property
    def attribution(self) -> str:
        """Get the attribution of the travel_time entity."""
        return None

    @property
    def destination(self) -> str:
        """Get the destination coordinates of the travel_time entity."""
        return None

    @property
    def destination_name(self) -> str:
        """Get the destination name of the travel_time entity."""
        return None

    @property
    def distance(self) -> str:
        """Get the distance of the travel_time entity."""
        return None

    @property
    def duration(self) -> str:
        """Get the duration without traffic of the travel_time entity."""
        return None

    @property
    def duration_in_traffic(self) -> str:
        """Get the duration with traffic of the travel_time entity."""
        return None

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return ICON_CAR

    @property
    def name(self) -> str:
        """Get the name of the travel_time entity."""
        return None

    @property
    def origin(self) -> str:
        """Get the origin coordinates of the travel_time entity."""
        return None

    @property
    def origin_name(self) -> str:
        """Get the origin name of the travel_time entity."""
        return None

    @property
    def route(self) -> str:
        """Get the route of the travel_time entity."""
        return None

    @property
    def state(self) -> Optional[str]:
        """Return the state of the travel_time entity."""
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def unit_system(self) -> str:
        """Get the unit system of the travel_time entity."""
        return self.hass.config.units.name

    @property
    def state_attributes(self,) -> Optional[Dict[str, Union[None, float, str, bool]]]:
        """Return the state attributes."""
        res = {}
        if self.attribution is not None:
            res[ATTR_ATTRIBUTION] = self.attribution

        if self.destination is not None:
            res[ATTR_DESTINATION] = self.destination

        if self.destination_name is not None:
            res[ATTR_DESTINATION_NAME] = self.destination_name

        if self.distance is not None:
            res[ATTR_DISTANCE] = self.distance

        if self.duration is not None:
            res[ATTR_DURATION] = self.duration

        if self.duration_in_traffic is not None:
            res[ATTR_DURATION_IN_TRAFFIC] = self.duration_in_traffic

        if self.origin is not None:
            res[ATTR_ORIGIN] = self.origin

        if self.origin_name is not None:
            res[ATTR_ORIGIN_NAME] = self.origin_name

        if self.route is not None:
            res[ATTR_ROUTE] = self.route

        if self.unit_system is not None:
            res[ATTR_UNIT_SYSTEM] = self.unit_system

        return res
