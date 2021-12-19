"""Support for the Brother service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BrotherDataUpdateCoordinator
from .const import DATA_CONFIG_ENTRY, DOMAIN

ATTR_BELT_UNIT_REMAINING_LIFE = "belt_unit_remaining_life"
ATTR_BLACK_DRUM_COUNTER = "black_drum_counter"
ATTR_BLACK_DRUM_REMAINING_LIFE = "black_drum_remaining_life"
ATTR_BLACK_DRUM_REMAINING_PAGES = "black_drum_remaining_pages"
ATTR_BLACK_INK_REMAINING = "black_ink_remaining"
ATTR_BLACK_TONER_REMAINING = "black_toner_remaining"
ATTR_BW_COUNTER = "b/w_counter"
ATTR_COLOR_COUNTER = "color_counter"
ATTR_COUNTER = "counter"
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
ATTR_REMAINING_PAGES = "remaining_pages"
ATTR_STATUS = "status"
ATTR_UPTIME = "uptime"
ATTR_YELLOW_DRUM_COUNTER = "yellow_drum_counter"
ATTR_YELLOW_DRUM_REMAINING_LIFE = "yellow_drum_remaining_life"
ATTR_YELLOW_DRUM_REMAINING_PAGES = "yellow_drum_remaining_pages"
ATTR_YELLOW_INK_REMAINING = "yellow_ink_remaining"
ATTR_YELLOW_TONER_REMAINING = "yellow_toner_remaining"

UNIT_PAGES = "p"

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Brother entities from a config_entry."""
    coordinator = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id]

    sensors = []

    device_info = DeviceInfo(
        configuration_url=f"http://{entry.data[CONF_HOST]}/",
        identifiers={(DOMAIN, coordinator.data.serial)},
        manufacturer=ATTR_MANUFACTURER,
        model=coordinator.data.model,
        name=coordinator.data.model,
        sw_version=getattr(coordinator.data, "firmware", None),
    )

    for description in SENSOR_TYPES:
        if description.key in coordinator.data:
            sensors.append(
                description.entity_class(coordinator, description, device_info)
            )
    async_add_entities(sensors, False)


class BrotherPrinterSensor(CoordinatorEntity, SensorEntity):
    """Define an Brother Printer sensor."""

    def __init__(
        self,
        coordinator: BrotherDataUpdateCoordinator,
        description: BrotherSensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attrs: dict[str, Any] = {}
        self._attr_device_info = device_info
        self._attr_name = f"{coordinator.data.model} {description.name}"
        self._attr_unique_id = f"{coordinator.data.serial.lower()}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return cast(
            StateType, getattr(self.coordinator.data, self.entity_description.key)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        remaining_pages, drum_counter = ATTRS_MAP.get(
            self.entity_description.key, (None, None)
        )
        if remaining_pages and drum_counter:
            self._attrs[ATTR_REMAINING_PAGES] = getattr(
                self.coordinator.data, remaining_pages
            )
            self._attrs[ATTR_COUNTER] = getattr(self.coordinator.data, drum_counter)
        return self._attrs


class BrotherPrinterUptimeSensor(BrotherPrinterSensor):
    """Define an Brother Printer Uptime sensor."""

    @property
    def native_value(self) -> datetime:
        """Return the state."""
        return cast(
            datetime, getattr(self.coordinator.data, self.entity_description.key)
        )


@dataclass
class BrotherSensorEntityDescription(SensorEntityDescription):
    """A class that describes sensor entities."""

    entity_class: type[BrotherPrinterSensor] = BrotherPrinterSensor


SENSOR_TYPES: tuple[BrotherSensorEntityDescription, ...] = (
    BrotherSensorEntityDescription(
        key=ATTR_STATUS,
        icon="mdi:printer",
        name=ATTR_STATUS.title(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_PAGE_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_PAGE_COUNTER.replace("_", " ").title(),
        native_unit_of_measurement=UNIT_PAGES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_BW_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_BW_COUNTER.replace("_", " ").title(),
        native_unit_of_measurement=UNIT_PAGES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_COLOR_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_COLOR_COUNTER.replace("_", " ").title(),
        native_unit_of_measurement=UNIT_PAGES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_DUPLEX_COUNTER,
        icon="mdi:file-document-outline",
        name=ATTR_DUPLEX_COUNTER.replace("_", " ").title(),
        native_unit_of_measurement=UNIT_PAGES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_BLACK_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_BLACK_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_CYAN_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_CYAN_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_MAGENTA_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_MAGENTA_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_YELLOW_DRUM_REMAINING_LIFE,
        icon="mdi:chart-donut",
        name=ATTR_YELLOW_DRUM_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_BELT_UNIT_REMAINING_LIFE,
        icon="mdi:current-ac",
        name=ATTR_BELT_UNIT_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_FUSER_REMAINING_LIFE,
        icon="mdi:water-outline",
        name=ATTR_FUSER_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_LASER_REMAINING_LIFE,
        icon="mdi:spotlight-beam",
        name=ATTR_LASER_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_PF_KIT_1_REMAINING_LIFE,
        icon="mdi:printer-3d",
        name=ATTR_PF_KIT_1_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_PF_KIT_MP_REMAINING_LIFE,
        icon="mdi:printer-3d",
        name=ATTR_PF_KIT_MP_REMAINING_LIFE.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_BLACK_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_BLACK_TONER_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_CYAN_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_CYAN_TONER_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_MAGENTA_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_MAGENTA_TONER_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_YELLOW_TONER_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_YELLOW_TONER_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_BLACK_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_BLACK_INK_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_CYAN_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_CYAN_INK_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_MAGENTA_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_MAGENTA_INK_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_YELLOW_INK_REMAINING,
        icon="mdi:printer-3d-nozzle",
        name=ATTR_YELLOW_INK_REMAINING.replace("_", " ").title(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BrotherSensorEntityDescription(
        key=ATTR_UPTIME,
        name=ATTR_UPTIME.title(),
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_class=BrotherPrinterUptimeSensor,
    ),
)
