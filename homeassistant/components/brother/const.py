"""Constants for Brother integration."""
from homeassistant.const import UNIT_PERCENTAGE

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
ATTR_ICON = "icon"
ATTR_LABEL = "label"
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
ATTR_UNIT = "unit"
ATTR_UPTIME = "uptime"
ATTR_YELLOW_DRUM_COUNTER = "yellow_drum_counter"
ATTR_YELLOW_DRUM_REMAINING_LIFE = "yellow_drum_remaining_life"
ATTR_YELLOW_DRUM_REMAINING_PAGES = "yellow_drum_remaining_pages"
ATTR_YELLOW_INK_REMAINING = "yellow_ink_remaining"
ATTR_YELLOW_TONER_REMAINING = "yellow_toner_remaining"

DOMAIN = "brother"

UNIT_PAGES = "p"

PRINTER_TYPES = ["laser", "ink"]

SENSOR_TYPES = {
    ATTR_STATUS: {
        ATTR_ICON: "mdi:printer",
        ATTR_LABEL: ATTR_STATUS.title(),
        ATTR_UNIT: None,
    },
    ATTR_PAGE_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_PAGE_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
    },
    ATTR_BW_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_BW_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
    },
    ATTR_COLOR_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_COLOR_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
    },
    ATTR_DUPLEX_COUNTER: {
        ATTR_ICON: "mdi:file-document-outline",
        ATTR_LABEL: ATTR_DUPLEX_COUNTER.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PAGES,
    },
    ATTR_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_BLACK_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_BLACK_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_CYAN_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_CYAN_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_MAGENTA_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_MAGENTA_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_YELLOW_DRUM_REMAINING_LIFE: {
        ATTR_ICON: "mdi:chart-donut",
        ATTR_LABEL: ATTR_YELLOW_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_BELT_UNIT_REMAINING_LIFE: {
        ATTR_ICON: "mdi:current-ac",
        ATTR_LABEL: ATTR_BELT_UNIT_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_FUSER_REMAINING_LIFE: {
        ATTR_ICON: "mdi:water-outline",
        ATTR_LABEL: ATTR_FUSER_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_LASER_REMAINING_LIFE: {
        ATTR_ICON: "mdi:spotlight-beam",
        ATTR_LABEL: ATTR_LASER_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_PF_KIT_1_REMAINING_LIFE: {
        ATTR_ICON: "mdi:printer-3d",
        ATTR_LABEL: ATTR_PF_KIT_1_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_PF_KIT_MP_REMAINING_LIFE: {
        ATTR_ICON: "mdi:printer-3d",
        ATTR_LABEL: ATTR_PF_KIT_MP_REMAINING_LIFE.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_BLACK_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_BLACK_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_CYAN_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_CYAN_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_MAGENTA_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_MAGENTA_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_YELLOW_TONER_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_YELLOW_TONER_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_BLACK_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_BLACK_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_CYAN_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_CYAN_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_MAGENTA_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_MAGENTA_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_YELLOW_INK_REMAINING: {
        ATTR_ICON: "mdi:printer-3d-nozzle",
        ATTR_LABEL: ATTR_YELLOW_INK_REMAINING.replace("_", " ").title(),
        ATTR_UNIT: UNIT_PERCENTAGE,
    },
    ATTR_UPTIME: {ATTR_ICON: None, ATTR_LABEL: ATTR_UPTIME.title(), ATTR_UNIT: None},
}
