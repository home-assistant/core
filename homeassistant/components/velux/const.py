"""Constants for the Velux integration."""

from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "velux"
PLATFORMS = [Platform.COVER, Platform.LIGHT, Platform.SCENE]
LOGGER = getLogger(__package__)
