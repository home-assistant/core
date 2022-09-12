"""Sensor for HaFAS."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import Any

from pyhafas import HafasClient
from pyhafas.profile import DBProfile, VSNProfile
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_OFFSET
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

DOMAIN = "hafas"

CONF_PROFILE = "profile"
CONF_DESTINATION = "to"
CONF_START = "from"
DEFAULT_OFFSET = timedelta(minutes=0)
CONF_ONLY_DIRECT = "only_direct"
DEFAULT_ONLY_DIRECT = False

ICON = "mdi:train"

SCAN_INTERVAL = timedelta(minutes=2)


class Profile(Enum):
    """Enum of HaFAS profile type."""

    DB = 0
    VSN = 1


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PROFILE): cv.enum(Profile),
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_START): cv.string,
        vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): cv.time_period,
        vol.Optional(CONF_ONLY_DIRECT, default=DEFAULT_ONLY_DIRECT): cv.boolean,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HaFAS."""
    profile = config.get(CONF_PROFILE)
    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)
    offset = config.get(CONF_OFFSET)
    only_direct = config.get(CONF_ONLY_DIRECT)

    add_entities([HaFAS(profile, start, destination, offset, only_direct)], True)


class HaFAS(SensorEntity):
    """Implementation of a HaFAS sensor."""

    def __init__(self, profile, start, goal, offset, only_direct):
        """Initialize the sensor."""
        self._name = f"{start} to {goal}"
        self.offset = offset
        self.only_direct = only_direct

        self.client = None
        if profile == Profile.DB:
            self.client = HafasClient(DBProfile())
        elif profile == Profile.VSN:
            self.client = HafasClient(VSNProfile())

        origins = self.client.locations(start)
        self.origin = origins[0]

        destinations = self.client.locations(goal)
        self.destination = destinations[0]

        self.update()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon for the frontend."""
        return ICON

    @property
    def native_value(self) -> str:
        """Return the departure time of the next train."""
        if len(self.journeys) == 0 or len(self.journeys[0].legs) == 0:
            return "No connection possible"

        first_leg = self.journeys[0].legs[0]

        value = first_leg.departure.strftime("%H:%M")
        if (
            first_leg.departureDelay is not None
            and first_leg.departureDelay != timedelta()
        ):
            delay = int(first_leg.departureDelay.total_seconds() // 60)

            value += f" + {delay}"

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if len(self.journeys) == 0 or len(self.journeys[0].legs) == 0:
            return {}

        journey = self.journeys[0]
        first_leg = journey.legs[0]
        last_leg = journey.legs[-1]
        products = ", ".join([x.name for x in journey.legs])[:-2]
        duration = timedelta() if journey.duration is None else journey.duration
        delay = (
            timedelta()
            if first_leg.departureDelay is None
            else first_leg.departureDelay
        )
        delay_arrival = (
            timedelta() if last_leg.arrivalDelay is None else last_leg.arrivalDelay
        )

        connections = {
            "departure": first_leg.departure,
            "arrival": last_leg.arrival,
            "transfers": len(journey.legs) - 1,
            "time": str(duration),
            "products": products,
            "ontime": delay == timedelta(),
            "delay": str(delay),
            "canceled": first_leg.cancelled,
            "delay_arrival": str(delay_arrival),
        }

        if len(self.journeys) > 1:
            connections["next"] = self.journeys[1].legs[0].departure

        if len(self.journeys) > 2:
            connections["next_on"] = self.journeys[2].legs[0].departure

        return connections

    def update(self) -> None:
        """Get the latest delay from bahn.de and updates the state."""
        self.journeys = self.client.journeys(
            origin=self.origin,
            destination=self.destination,
            date=dt_util.as_local(dt_util.utcnow() + self.offset),
            max_changes=0 if self.only_direct else -1,
            max_journeys=3,
        )
