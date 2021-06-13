"""Constants for Brother integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
)

from .model import SensorDescription

ATTR_BELT_UNIT_REMAINING_LIFE: Final = "belt_unit_remaining_life"
ATTR_BLACK_DRUM_COUNTER: Final = "black_drum_counter"
ATTR_BLACK_DRUM_REMAINING_LIFE: Final = "black_drum_remaining_life"
ATTR_BLACK_DRUM_REMAINING_PAGES: Final = "black_drum_remaining_pages"
ATTR_BLACK_INK_REMAINING: Final = "black_ink_remaining"
ATTR_BLACK_TONER_REMAINING: Final = "black_toner_remaining"
ATTR_BW_COUNTER: Final = "b/w_counter"
ATTR_COLOR_COUNTER: Final = "color_counter"
ATTR_COUNTER: Final = "counter"
ATTR_CYAN_DRUM_COUNTER: Final = "cyan_drum_counter"
ATTR_CYAN_DRUM_REMAINING_LIFE: Final = "cyan_drum_remaining_life"
ATTR_CYAN_DRUM_REMAINING_PAGES: Final = "cyan_drum_remaining_pages"
ATTR_CYAN_INK_REMAINING: Final = "cyan_ink_remaining"
ATTR_CYAN_TONER_REMAINING: Final = "cyan_toner_remaining"
ATTR_DRUM_COUNTER: Final = "drum_counter"
ATTR_DRUM_REMAINING_LIFE: Final = "drum_remaining_life"
ATTR_DRUM_REMAINING_PAGES: Final = "drum_remaining_pages"
ATTR_DUPLEX_COUNTER: Final = "duplex_unit_pages_counter"
ATTR_ENABLED: Final = "enabled"
ATTR_FUSER_REMAINING_LIFE: Final = "fuser_remaining_life"
ATTR_LABEL: Final = "label"
ATTR_LASER_REMAINING_LIFE: Final = "laser_remaining_life"
ATTR_MAGENTA_DRUM_COUNTER: Final = "magenta_drum_counter"
ATTR_MAGENTA_DRUM_REMAINING_LIFE: Final = "magenta_drum_remaining_life"
ATTR_MAGENTA_DRUM_REMAINING_PAGES: Final = "magenta_drum_remaining_pages"
ATTR_MAGENTA_INK_REMAINING: Final = "magenta_ink_remaining"
ATTR_MAGENTA_TONER_REMAINING: Final = "magenta_toner_remaining"
ATTR_MANUFACTURER: Final = "Brother"
ATTR_PAGE_COUNTER: Final = "page_counter"
ATTR_PF_KIT_1_REMAINING_LIFE: Final = "pf_kit_1_remaining_life"
ATTR_PF_KIT_MP_REMAINING_LIFE: Final = "pf_kit_mp_remaining_life"
ATTR_REMAINING_PAGES: Final = "remaining_pages"
ATTR_STATUS: Final = "status"
ATTR_UNIT: Final = "unit"
ATTR_UPTIME: Final = "uptime"
ATTR_YELLOW_DRUM_COUNTER: Final = "yellow_drum_counter"
ATTR_YELLOW_DRUM_REMAINING_LIFE: Final = "yellow_drum_remaining_life"
ATTR_YELLOW_DRUM_REMAINING_PAGES: Final = "yellow_drum_remaining_pages"
ATTR_YELLOW_INK_REMAINING: Final = "yellow_ink_remaining"
ATTR_YELLOW_TONER_REMAINING: Final = "yellow_toner_remaining"

DATA_CONFIG_ENTRY: Final = "config_entry"

DOMAIN: Final = "brother"

UNIT_PAGES: Final = "p"

PRINTER_TYPES: Final = ["laser", "ink"]

SNMP: Final = "snmp"

ATTRS_MAP: Final[dict[str, tuple[str, str]]] = {
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

SENSOR_TYPES: Final[dict[str, SensorDescription]] = {
    ATTR_STATUS: {
        ATTR_ICON: "mdi:printer",
        ATTR_LABEL: ATTR_STATUS.title(),
        ATTR_UNIT: None,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: None,
    },
    ATTR_PAGE_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_PAGE_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_BW_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_BW_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_COLOR_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_COLOR_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_DUPLEX_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_DUPLEX_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_BLACK_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_BLACK_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_CYAN_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_CYAN_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_MAGENTA_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_MAGENTA_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_YELLOW_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_YELLOW_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_BELT_UNIT_REMAINING_LIFE: {
        ATTR_ICON: "mdi:current-ac",
        ATTR_LABEL: ATTR_BELT_UNIT_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_FUSER_REMAINING_LIFE: {
        ATTR_ICON: "mdi:water-outline",
        ATTR_LABEL: ATTR_FUSER_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_LASER_REMAINING_LIFE: {
        ATTR_ICON: "mdi:spotlight-beam",
        ATTR_LABEL: ATTR_LASER_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_PF_KIT_1_REMAINING_LIFE: {
        ATTR_ICON: "mdi:printer-3d",
        ATTR_LABEL: ATTR_PF_KIT_1_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_PF_KIT_MP_REMAINING_LIFE: {
        ATTR_ICON: "mdi:printer-3d",
        ATTR_LABEL: ATTR_PF_KIT_MP_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_BLACK_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_BLACK_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_CYAN_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_CYAN_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_MAGENTA_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_MAGENTA_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_YELLOW_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_YELLOW_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_BLACK_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_BLACK_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_CYAN_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_CYAN_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_MAGENTA_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_MAGENTA_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_YELLOW_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_YELLOW_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: PERCENTAGE,
        ATTR_ENABLED: True,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
    },
    ATTR_UPTIME: {
        ATTR_ICON: None,
        ATTR_LABEL: ATTR_UPTIME.title(),
        ATTR_UNIT: None,
        ATTR_ENABLED: False,
        ATTR_STATE_CLASS: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
}
