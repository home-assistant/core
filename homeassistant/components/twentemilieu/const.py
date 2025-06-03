"""Constants for the Twente Milieu integration."""

from datetime import timedelta
import logging
from typing import Final

from twentemilieu import WasteType

DOMAIN: Final = "twentemilieu"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

CONF_POST_CODE = "post_code"
CONF_HOUSE_NUMBER = "house_number"
CONF_HOUSE_LETTER = "house_letter"

WASTE_TYPE_TO_DESCRIPTION = {
    WasteType.NON_RECYCLABLE: "Non-recyclable waste pickup",
    WasteType.ORGANIC: "Organic waste pickup",
    WasteType.PACKAGES: "Packages waste pickup",
    WasteType.PAPER: "Paper waste pickup",
    WasteType.TREE: "Christmas tree pickup",
}
