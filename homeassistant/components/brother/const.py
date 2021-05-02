"""Constants for Brother integration."""
from __future__ import annotations

from typing import TypedDict

from homeassistant.const import PERCENTAGE

ATTR_BELT_UNIT_REMAINING_LIFE = "belt_unit_remaining_life"
ATTR_BLACK_DRUM_COUNTER = "black_drum_counter"
ATTR_BLACK_DRUM_REMAINING_LIFE = "black_drum_remaining_life"
ATTR_BLACK_DRUM_REMAINING_PAGES = "black_drum_remaining_pages"
ATTR_BLACK_INK_REMAINING = "black_ink_remaining"
ATTR_BLACK_TONER_REMAINING = "black_toner_remaining"
ATTR_BW_COUNTER = "b/w_counter"
ATTR_COLOR_COUNTER = "color_counter"
ATTR_CYAN_DRUM_COUNTER = "cyan_drum_counter"
ATTR_CYAN_DRUM_REMAINING_LIFE = "cyan_drum_remaining_life"
ATTR_CYAN_DRUM_REMAINING_PAGES = "cyan_drum_remaining_pages"
ATTR_CYAN_INK_REMAINING = "cyan_ink_remaining"
ATTR_CYAN_TONER_REMAINING = "cyan_toner_remaining"
ATTR_DRUM_COUNTER = "drum_counter"
ATTR_DRUM_REMAINING_LIFE = "drum_remaining_life"
ATTR_DRUM_REMAINING_PAGES = "drum_remaining_pages"
ATTR_DUPLEX_COUNTER = "duplex_unit_pages_counter"
ATTR_FUSER_REMAINING_LIFE = "fuser_remaining_life"
ATTR_LASER_REMAINING_LIFE = "laser_remaining_life"
ATTR_MAGENTA_DRUM_COUNTER = "magenta_drum_counter"
ATTR_MAGENTA_DRUM_REMAINING_LIFE = "magenta_drum_remaining_life"
ATTR_MAGENTA_DRUM_REMAINING_PAGES = "magenta_drum_remaining_pages"
ATTR_MAGENTA_INK_REMAINING = "magenta_ink_remaining"
ATTR_MAGENTA_TONER_REMAINING = "magenta_toner_remaining"
ATTR_MANUFACTURER = "Brother"
ATTR_PAGE_COUNTER = "page_counter"
ATTR_PF_KIT_1_REMAINING_LIFE = "pf_kit_1_remaining_life"
ATTR_PF_KIT_MP_REMAINING_LIFE = "pf_kit_mp_remaining_life"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"
ATTR_YELLOW_DRUM_COUNTER = "yellow_drum_counter"
ATTR_YELLOW_DRUM_REMAINING_LIFE = "yellow_drum_remaining_life"
ATTR_YELLOW_DRUM_REMAINING_PAGES = "yellow_drum_remaining_pages"
ATTR_YELLOW_INK_REMAINING = "yellow_ink_remaining"
ATTR_YELLOW_TONER_REMAINING = "yellow_toner_remaining"

DATA_CONFIG_ENTRY = "config_entry"

DOMAIN = "brother"

UNIT_PAGES = "p"

PRINTER_TYPES = ["laser", "ink"]

SNMP = "snmp"

ATTRS_MAP: dict[str, tuple[str, str]] = {
    ATTR_DRUM_REMAINING_LIFE: (ATTR_DRUM_REMAINING_PAGES, ATTR_DRUM_COUNTER),
    ATTR_BLACK_DRUM_REMAINING_LIFE: (
        ATTR_BLACK_DRUM_REMAINING_PAGES,
        ATTR_BLACK_DRUM_COUNTER,
    ),
    ATTR_CYAN_DRUM_REMAINING_LIFE: (
        ATTR_CYAN_DRUM_REMAINING_PAGES,
        ATTR_CYAN_DRUM_COUNTER,
    ),
    ATTR_MAGENTA_DRUM_REMAINING_LIFE: (
        ATTR_MAGENTA_DRUM_REMAINING_PAGES,
        ATTR_MAGENTA_DRUM_COUNTER,
    ),
    ATTR_YELLOW_DRUM_REMAINING_LIFE: (
        ATTR_YELLOW_DRUM_REMAINING_PAGES,
        ATTR_YELLOW_DRUM_COUNTER,
    ),
}

SENSOR_TYPES: dict[str, SensorDescription] = {
    ATTR_STATUS: {
        "icon": "mdi:printer",
        "label": ATTR_STATUS.title(),
        "unit": None,
        "enabled": True,
    },
    ATTR_PAGE_COUNTER: {
        "icon": "mdi:file-document-outline",
        "label": ATTR_PAGE_COUNTER.replace("_", " ").title(),
        "unit": UNIT_PAGES,
        "enabled": True,
    },
    ATTR_BW_COUNTER: {
        "icon": "mdi:file-document-outline",
        "label": ATTR_BW_COUNTER.replace("_", " ").title(),
        "unit": UNIT_PAGES,
        "enabled": True,
    },
    ATTR_COLOR_COUNTER: {
        "icon": "mdi:file-document-outline",
        "label": ATTR_COLOR_COUNTER.replace("_", " ").title(),
        "unit": UNIT_PAGES,
        "enabled": True,
    },
    ATTR_DUPLEX_COUNTER: {
        "icon": "mdi:file-document-outline",
        "label": ATTR_DUPLEX_COUNTER.replace("_", " ").title(),
        "unit": UNIT_PAGES,
        "enabled": True,
    },
    ATTR_DRUM_REMAINING_LIFE: {
        "icon": "mdi:chart-donut",
        "label": ATTR_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_BLACK_DRUM_REMAINING_LIFE: {
        "icon": "mdi:chart-donut",
        "label": ATTR_BLACK_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_CYAN_DRUM_REMAINING_LIFE: {
        "icon": "mdi:chart-donut",
        "label": ATTR_CYAN_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_MAGENTA_DRUM_REMAINING_LIFE: {
        "icon": "mdi:chart-donut",
        "label": ATTR_MAGENTA_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_YELLOW_DRUM_REMAINING_LIFE: {
        "icon": "mdi:chart-donut",
        "label": ATTR_YELLOW_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_BELT_UNIT_REMAINING_LIFE: {
        "icon": "mdi:current-ac",
        "label": ATTR_BELT_UNIT_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_FUSER_REMAINING_LIFE: {
        "icon": "mdi:water-outline",
        "label": ATTR_FUSER_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_LASER_REMAINING_LIFE: {
        "icon": "mdi:spotlight-beam",
        "label": ATTR_LASER_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_PF_KIT_1_REMAINING_LIFE: {
        "icon": "mdi:printer-3d",
        "label": ATTR_PF_KIT_1_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_PF_KIT_MP_REMAINING_LIFE: {
        "icon": "mdi:printer-3d",
        "label": ATTR_PF_KIT_MP_REMAINING_LIFE.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_BLACK_TONER_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_BLACK_TONER_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_CYAN_TONER_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_CYAN_TONER_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_MAGENTA_TONER_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_MAGENTA_TONER_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_YELLOW_TONER_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_YELLOW_TONER_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_BLACK_INK_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_BLACK_INK_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_CYAN_INK_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_CYAN_INK_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_MAGENTA_INK_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_MAGENTA_INK_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_YELLOW_INK_REMAINING: {
        "icon": "mdi:printer-3d-nozzle",
        "label": ATTR_YELLOW_INK_REMAINING.replace("_", " ").title(),
        "unit": PERCENTAGE,
        "enabled": True,
    },
    ATTR_UPTIME: {
        "icon": None,
        "label": ATTR_UPTIME.title(),
        "unit": None,
        "enabled": False,
    },
}


class SensorDescription(TypedDict):
    """Sensor description class."""

    icon: str | None
    label: str
    unit: str | None
    enabled: bool
