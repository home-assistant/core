"""Adds constants for brottsplatskartan integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "brottsplatskartan"
PLATFORMS = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

CONF_AREA = "area"
CONF_APP_ID = "app_id"
DEFAULT_NAME = "Brottsplatskartan"

AREAS = [
    "none",
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
