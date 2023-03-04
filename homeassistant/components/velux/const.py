"""Constants for the Velux integration."""
from logging import getLogger

from homeassistant.const import Platform

DOMAIN = "velux"
DATA_VELUX = "data_velux"
PLATFORMS = [Platform.COVER, Platform.LIGHT, Platform.SCENE]
_LOGGER = getLogger(__name__)
