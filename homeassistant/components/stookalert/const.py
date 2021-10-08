"""Constants for the Stookalert integration."""
import logging
from typing import Final

DOMAIN: Final = "stookalert"
LOGGER = logging.getLogger(__package__)

CONF_PROVINCE: Final = "province"

PROVINCES: Final = (
    "Drenthe",
    "Flevoland",
    "Friesland",
    "Gelderland",
    "Groningen",
    "Limburg",
    "Noord-Brabant",
    "Noord-Holland",
    "Overijssel",
    "Utrecht",
    "Zeeland",
    "Zuid-Holland",
)

ATTR_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_SERVICE: Final = "service"
