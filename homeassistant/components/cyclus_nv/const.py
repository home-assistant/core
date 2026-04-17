"""Constants for the Cyclus NV integration."""

from datetime import timedelta
import logging
from typing import Final

from cyclus.const import WasteType

DOMAIN: Final = "cyclus_nv"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=4)

CONF_HOUSE_NUMBER = "house_number"
CONF_ZIPCODE = "zipcode"
CONF_BAG_ID = "bag_id"

WASTE_TYPE_TO_DESCRIPTION: dict[WasteType, str] = {
    WasteType.GFT: "GFT waste pickup",
    WasteType.RESIDUAL_WASTE: "Residual waste pickup",
    WasteType.PAPER: "Paper waste pickup",
    WasteType.CONSTRUCTION_WASTE: "Construction waste pickup",
    WasteType.ELECTRICAL_APPLIANCES: "Electrical appliances pickup",
    WasteType.GLASS: "Glass waste pickup",
    WasteType.THRIFT_STORE: "Thrift store pickup",
    WasteType.LARGE_HOUSEHOLD_WASTE: "Large household waste pickup",
    WasteType.HAZARDOUS_WASTE: "Hazardous waste pickup",
    WasteType.TEXTILES: "Textiles pickup",
    WasteType.ASBESTOS: "Asbestos pickup",
    WasteType.RECYCLING_CENTER: "Recycling center",
    WasteType.PMD: "PMD waste pickup",
    WasteType.NOTIFICATION_FORM: "Notification form",
    WasteType.MOBILE_RECYCLING_CENTER: "Mobile recycling center",
    WasteType.CHRISTMAS_TREES: "Christmas tree pickup",
    WasteType.GARDEN_WASTE: "Garden waste pickup",
    WasteType.DEMOLITION_COMPANY: "Demolition company",
}
