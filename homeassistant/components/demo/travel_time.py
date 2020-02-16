"""Support for travel time sensors."""
import random
from typing import Callable, Dict, Optional, Union

import voluptuous as vol

from homeassistant.components.travel_time import TRAVEL_TIME_SCHEMA, TravelTimeEntity
from homeassistant.components.travel_time.const import (
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_DESTINATION_NAME,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ORIGIN_NAME,
    CONF_TRAVEL_MODE,
    ICON_BICYCLE,
    ICON_CAR,
    ICON_PEDESTRIAN,
    ICON_PUBLIC,
    ICON_TRUCK,
)
from homeassistant.const import CONF_MODE, CONF_NAME, EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "Demo Travel Time"

TRAVEL_MODE_BICYCLE = "bicycle"
TRAVEL_MODE_CAR = "car"
TRAVEL_MODE_PEDESTRIAN = "pedestrian"
TRAVEL_MODE_PUBLIC = "publicTransport"
TRAVEL_MODE_TRUCK = "truck"

TRAVEL_TIME_SCHEMA = TRAVEL_TIME_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TRAVEL_MODE, default=TRAVEL_MODE_CAR): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable,
    discovery_info: None = None,
) -> None:
    """Set up the Demo travel time platform."""

    origin_latitude = config.get(CONF_ORIGIN_LATITUDE)
    origin_longitude = config.get(CONF_ORIGIN_LONGITUDE)
    origin_name = config.get(CONF_ORIGIN_NAME)
    destination_latitude = config.get(CONF_DESTINATION_LATITUDE)
    destination_longitude = config.get(CONF_DESTINATION_LONGITUDE)
    destination_name = config.get(CONF_DESTINATION_NAME)

    name = config[CONF_NAME]
    travel_mode = config[CONF_MODE]

    travel_time_entity = DemoTravelTimeEntity(
        name,
        origin_latitude,
        origin_longitude,
        origin_name,
        destination_latitude,
        destination_longitude,
        destination_name,
        travel_mode,
    )

    async_add_entities([travel_time_entity])


class DemoTravelTimeEntity(TravelTimeEntity):
    """Representation of Demo travel_time."""

    def __init__(
        self,
        name: str,
        origin_latitude: Union[template.Template, float],
        origin_longitude: Union[template.Template, float],
        origin_name: Union[template.Template, str],
        destination_latitude: Union[template.Template, float],
        destination_longitude: Union[template.Template, float],
        destination_name: Union[template.Template, str],
        travel_mode: str,
    ) -> None:
        """Initialize the travel_time entity."""
        self._name = name
        self._origin_latitude = origin_latitude
        self._origin_longitude = origin_longitude
        self._origin_name = origin_name
        self._destination_latitude = destination_latitude
        self._destination_longitude = destination_longitude
        self._destination_name = destination_name
        self._travel_mode = travel_mode
        self._origin = None
        self._origin_address = None
        self._destination = None
        self._destination_address = None
        self._distance = None
        self._duration = None
        self._duration_in_traffic = None
        self._route = None
        self._resolved_origin_name = None
        self._resolved_destination_name = None

    async def async_added_to_hass(self) -> None:
        """Delay the travel_time update to avoid entity not found warnings."""

        @callback
        def delayed_travel_time_update(event):
            """Update travel_time after homeassistant started."""
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, delayed_travel_time_update
        )

    @property
    def attribution(self) -> str:
        """Get the attribution of the travel_time entity."""
        return None

    @property
    def destination(self) -> str:
        """Get the destination coordinates of the travel_time entity."""
        return self._destination

    @property
    def destination_address(self) -> str:
        """Get the destination address of the travel_time entity."""
        if self._destination_address is not None:
            return self._destination_address

    @property
    def distance(self) -> str:
        """Get the distance of the travel_time entity."""
        if self._distance is not None:
            return self._distance

    @property
    def duration(self) -> str:
        """Get the duration without traffic of the travel_time entity."""
        if self._duration is not None:
            return self._duration / 60

    @property
    def duration_in_traffic(self) -> str:
        """Get the duration with traffic of the travel_time entity."""
        if self._duration_in_traffic is not None:
            return self._duration_in_traffic / 60

    @property
    def icon(self) -> str:
        """Icon to use in the frontend depending on travel_mode."""
        if self._travel_mode == TRAVEL_MODE_BICYCLE:
            return ICON_BICYCLE
        if self._travel_mode == TRAVEL_MODE_PEDESTRIAN:
            return ICON_PEDESTRIAN
        if self._travel_mode == TRAVEL_MODE_PUBLIC:
            return ICON_PUBLIC
        if self._travel_mode == TRAVEL_MODE_TRUCK:
            return ICON_TRUCK
        return ICON_CAR

    @property
    def travel_mode(self) -> str:
        """Get the mode of travelling e.g car for this entity."""
        if self._travel_mode is not None:
            return self._travel_mode

    @property
    def name(self) -> str:
        """Get the name of the travel_time entity."""
        return self._name

    @property
    def origin(self) -> str:
        """Get the origin coordinates of the travel_time entity."""
        if self._origin is not None:
            return self._origin

    @property
    def origin_address(self) -> str:
        """Get the origin address of the travel_time entity."""
        if self._origin_address is not None:
            return self._origin_address

    @property
    def route(self) -> str:
        """Get the route of the travel_time entity."""
        if self._route is not None:
            return self._route

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self._duration_in_traffic is not None:
            return str(round(self._duration_in_traffic / 60))

    async def async_update(self) -> None:
        """Update Sensor Information."""
        if self._origin_name is not None:
            origin_name = await self.async_try_resolve_template(self._origin_name)
        else:
            origin_latitude = await self.async_try_resolve_template(
                self._origin_latitude
            )
            origin_longitude = await self.async_try_resolve_template(
                self._origin_longitude
            )

        if self._destination_name is not None:
            destination_name = await self.async_try_resolve_template(
                self._destination_name
            )
        else:
            destination_latitude = await self.async_try_resolve_template(
                self._destination_latitude
            )
            destination_longitude = await self.async_try_resolve_template(
                self._destination_longitude
            )

        if origin_name is not None:
            if destination_name is not None:
                api_result = self.dummy_result(origin_name, destination_name)
            else:
                api_result = self.dummy_result(
                    origin_name, [destination_latitude, destination_longitude]
                )
        elif destination_name is not None:
            api_result = self.dummy_result(
                [origin_latitude, origin_longitude], destination_name
            )
        else:
            api_result = self.dummy_result(
                [origin_latitude, origin_longitude],
                [destination_latitude, destination_longitude],
            )

        self._origin_address = api_result["origin_address"]
        self._duration_in_traffic = api_result["duration_in_traffic"]
        self._duration = api_result["duration"]
        self._distance = api_result["distance"]
        self._route = api_result["route"]
        self._destination_address = api_result["destination_address"]

    # pylint: disable=no-self-use
    def dummy_result(
        self, origin: Union[list, str], destination: Union[list, str]
    ) -> dict:
        """Get data from an API call."""
        return {
            "origin_address": "Originstreet 9, Demo City",
            "duration_in_traffic": random.randrange(300, 900),
            "duration": 1000,
            "distance": random.randrange(50, 150),
            "route": "Demo Way; Demo Street; Demo Place",
            "destination_address": "Destinationstreet 9, Demo City",
        }

    async def async_try_resolve_template(self, attribute):
        """If the attribute is a template resolve it."""
        if isinstance(attribute, template.Template):
            return await attribute.async_render()
        return attribute
