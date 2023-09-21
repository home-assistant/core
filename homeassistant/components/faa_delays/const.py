"""Constants for the FAA Delays integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntityDescription

LOGGER = logging.getLogger(__name__)

DOMAIN = "faa_delays"

FAA_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="GROUND_DELAY",
        name="Ground Delay",
        icon="mdi:airport",
    ),
    BinarySensorEntityDescription(
        key="GROUND_STOP",
        name="Ground Stop",
        icon="mdi:airport",
    ),
    BinarySensorEntityDescription(
        key="DEPART_DELAY",
        name="Departure Delay",
        icon="mdi:airplane-takeoff",
    ),
    BinarySensorEntityDescription(
        key="ARRIVE_DELAY",
        name="Arrival Delay",
        icon="mdi:airplane-landing",
    ),
    BinarySensorEntityDescription(
        key="CLOSURE",
        name="Closure",
        icon="mdi:airplane:off",
    ),
)
