"""The travel_time integration."""
from datetime import timedelta
import logging
from typing import Dict, Optional, Union

import voluptuous as vol

from homeassistant.const import ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass

from .const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_MODE,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    ATTR_ROUTE_MODE,
    ATTR_TRAFFIC_MODE,
    ATTR_UNIT_SYSTEM,
    DOMAIN,
    UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


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
        return await get_location_from_entity(hass, entity.state, recursion_history)

    # Check if state is valid coordinate set
    if _entity_state_is_valid_coordinate_set(entity.state):
        return entity.state

    _LOGGER.error(
        "The state of %s is not a valid set of coordinates: %s", entity_id, entity.state
    )
    return None


def _entity_state_is_valid_coordinate_set(state: str) -> bool:
    """Check that the given string is a valid set of coordinates."""
    schema = vol.Schema(cv.gps)
    try:
        coordinates = state.split(",")
        schema(coordinates)
        return True
    except (vol.MultipleInvalid):
        return False


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
        return None

    @property
    def mode(self) -> str:
        """Get the mode of travelling e.g car for this entity."""
        return None

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
    def route_mode(self) -> str:
        """Get the route_mode e.g fastest of the travel_time entity."""
        return None

    @property
    def state(self) -> Optional[str]:
        """Return the state of the travel_time entity."""
        return None

    @property
    def traffic_mode(self) -> Optional[str]:
        """Return if traffic_mode is enabled for this travel_time entity."""
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return UNIT_OF_MEASUREMENT

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

        if self.mode is not None:
            res[ATTR_MODE] = self.mode

        if self.origin is not None:
            res[ATTR_ORIGIN] = self.origin

        if self.origin_name is not None:
            res[ATTR_ORIGIN_NAME] = self.origin_name

        if self.route is not None:
            res[ATTR_ROUTE] = self.route

        if self.route_mode is not None:
            res[ATTR_ROUTE_MODE] = self.route_mode

        if self.traffic_mode is not None:
            res[ATTR_TRAFFIC_MODE] = self.traffic_mode

        if self.unit_system is not None:
            res[ATTR_UNIT_SYSTEM] = self.unit_system

        return res
