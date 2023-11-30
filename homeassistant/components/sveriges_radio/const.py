"""Constants for the Sveriges Radio integration."""
import logging
from typing import Final

DOMAIN: Final = "sveriges_radio"

LOGGER = logging.getLogger(__package__)

FOLDERNAME: Final = "Podcasts"

ERROR_MESSAGE_NOT_INITIALIZED: Final = "Sveriges Radio not initialized"

AREAS = [
    "Norrbotten",
    "Västerbotten",
    "Västernorrland",
    "Jämtland",
    "Gävleborg",
    "Dalarna",
    "Uppland",
    "Västmanland",
    "Örebro",
    "Värmland",
]
CONF_AREA = "area"
CONF_AREA_NAME = "Area"
CONF_AREA_ICON = "mdi:map-marker"
DATE = "createddate"
DATE_NAME = "Timestamp"
DATE_ICON = "mdi:update"
DESC = "description"
DESC_NAME = "Message"
DESC_ICON = "mdi:message"
LOC = "title"
LOC_NAME = "Exact Location"
LOC_ICON = "mdi:highway"
INFO = [
    (DESC, DESC_NAME, DESC_ICON),
    (CONF_AREA, CONF_AREA_NAME, CONF_AREA_ICON),
    (DATE, DATE_NAME, DATE_ICON),
    (LOC, LOC_NAME, LOC_ICON),
]

TITLE = "Sveriges Radio Traffic"
