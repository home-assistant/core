"""Sensor platform for Brottsplatskartan information."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import logging
import uuid

import brottsplatskartan
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_AREA = "area"

DEFAULT_NAME = "Brottsplatskartan"

SCAN_INTERVAL = timedelta(minutes=30)

AREAS = [
    "Blekinge län",
    "Dalarnas län",
    "Gotlands län",
    "Gävleborgs län",
    "Hallands län",
    "Jämtlands län",
    "Jönköpings län",
    "Kalmar län",
    "Kronobergs län",
    "Norrbottens län",
    "Skåne län",
    "Stockholms län",
    "Södermanlands län",
    "Uppsala län",
    "Värmlands län",
    "Västerbottens län",
    "Västernorrlands län",
    "Västmanlands län",
    "Västra Götalands län",
    "Örebro län",
    "Östergötlands län",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA, default=[]): vol.All(cv.ensure_list, [vol.In(AREAS)]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Brottsplatskartan platform."""

    area = config.get(CONF_AREA)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config[CONF_NAME]

    # Every Home Assistant instance should have their own unique
    # app parameter: https://brottsplatskartan.se/sida/api
    app = f"ha-{uuid.getnode()}"

    bpk = brottsplatskartan.BrottsplatsKartan(
        app=app, area=area, latitude=latitude, longitude=longitude
    )

    add_entities([BrottsplatskartanSensor(bpk, name)], True)


class BrottsplatskartanSensor(SensorEntity):
    """Representation of a Brottsplatskartan Sensor."""

    _attr_attribution = brottsplatskartan.ATTRIBUTION

    def __init__(self, bpk: brottsplatskartan.BrottsplatsKartan, name: str) -> None:
        """Initialize the Brottsplatskartan sensor."""
        self._brottsplatskartan = bpk
        self._attr_name = name

    def update(self) -> None:
        """Update device state."""

        incident_counts: defaultdict[str, int] = defaultdict(int)
        incidents = self._brottsplatskartan.get_incidents()

        if incidents is False:
            _LOGGER.debug("Problems fetching incidents")
            return

        for incident in incidents:
            if (incident_type := incident.get("title_type")) is not None:
                incident_counts[incident_type] += 1

        self._attr_extra_state_attributes = incident_counts
        self._attr_native_value = len(incidents)
