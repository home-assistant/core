"""Constants for Brother integration."""
from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, PERCENTAGE

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
ATTR_FUSER_REMAINING_LIFE: Final = "fuser_remaining_life"
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

SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=ATTR_STATUS,
        icon="mdi:printer",
        name=ATTR_STATUS.title(),
    ),
    SensorEntityDescription(
        key=ATTR_PAGE_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_PAGE_COUNTER.replace("_", " ").title(),
        unit_of_measurement=UNIT_PAGES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BW_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_BW_COUNTER.replace("_", " ").title(),
        unit_of_measurement=UNIT_PAGES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_COLOR_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_COLOR_COUNTER.replace("_", " ").title(),
        unit_of_measurement=UNIT_PAGES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DUPLEX_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_DUPLEX_COUNTER.replace("_", " ").title(),
        unit_of_measurement=UNIT_PAGES,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BLACK_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_BLACK_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_CYAN_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_CYAN_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_MAGENTA_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_MAGENTA_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_YELLOW_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_YELLOW_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BELT_UNIT_REMAINING_LIFE,
        icon="mdi:current-ac",
        name=ATTR_BELT_UNIT_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_FUSER_REMAINING_LIFE,
        icon="mdi:water-outline",
        name=ATTR_FUSER_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_LASER_REMAINING_LIFE,
        icon="mdi:spotlight-beam",
        name=ATTR_LASER_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_PF_KIT_1_REMAINING_LIFE,
        icon="mdi:printer-3d",
        name=ATTR_PF_KIT_1_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_PF_KIT_MP_REMAINING_LIFE,
        icon="mdi:printer-3d",
        name=ATTR_PF_KIT_MP_REMAINING_LIFE.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BLACK_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_BLACK_TONER_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_CYAN_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_CYAN_TONER_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_MAGENTA_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_MAGENTA_TONER_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_YELLOW_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_YELLOW_TONER_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BLACK_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_BLACK_INK_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_CYAN_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_CYAN_INK_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_MAGENTA_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_MAGENTA_INK_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_YELLOW_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_YELLOW_INK_REMAINING.replace("_", " ").title(),
        unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_UPTIME,
        name=ATTR_UPTIME.title(),
        entity_registry_enabled_default=False,
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
)
