"""Support for the Brother service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from brother import BrotherSensors

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BrotherConfigEntry, BrotherDataUpdateCoordinator

ATTR_COUNTER = "counter"
ATTR_REMAINING_PAGES = "remaining_pages"

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class BrotherSensorEntityDescription(SensorEntityDescription):
    """A class that describes sensor entities."""

    value: Callable[[BrotherSensors], StateType | datetime]


SENSOR_TYPES: tuple[BrotherSensorEntityDescription, ...] = (
    BrotherSensorEntityDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.status,
    ),
    BrotherSensorEntityDescription(
        key="page_counter",
        translation_key="page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.page_counter,
    ),
    BrotherSensorEntityDescription(
        key="bw_counter",
        translation_key="bw_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.bw_counter,
    ),
    BrotherSensorEntityDescription(
        key="color_counter",
        translation_key="color_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.color_counter,
    ),
    BrotherSensorEntityDescription(
        key="duplex_unit_pages_counter",
        translation_key="duplex_unit_page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.duplex_unit_pages_counter,
    ),
    BrotherSensorEntityDescription(
        key="drum_remaining_life",
        translation_key="drum_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.drum_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="drum_remaining_pages",
        translation_key="drum_remaining_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.drum_remaining_pages,
    ),
    BrotherSensorEntityDescription(
        key="drum_counter",
        translation_key="drum_page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.drum_counter,
    ),
    BrotherSensorEntityDescription(
        key="black_drum_remaining_life",
        translation_key="black_drum_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.black_drum_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="black_drum_remaining_pages",
        translation_key="black_drum_remaining_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.black_drum_remaining_pages,
    ),
    BrotherSensorEntityDescription(
        key="black_drum_counter",
        translation_key="black_drum_page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.black_drum_counter,
    ),
    BrotherSensorEntityDescription(
        key="cyan_drum_remaining_life",
        translation_key="cyan_drum_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.cyan_drum_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="cyan_drum_remaining_pages",
        translation_key="cyan_drum_remaining_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.cyan_drum_remaining_pages,
    ),
    BrotherSensorEntityDescription(
        key="cyan_drum_counter",
        translation_key="cyan_drum_page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.cyan_drum_counter,
    ),
    BrotherSensorEntityDescription(
        key="magenta_drum_remaining_life",
        translation_key="magenta_drum_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.magenta_drum_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="magenta_drum_remaining_pages",
        translation_key="magenta_drum_remaining_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.magenta_drum_remaining_pages,
    ),
    BrotherSensorEntityDescription(
        key="magenta_drum_counter",
        translation_key="magenta_drum_page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.magenta_drum_counter,
    ),
    BrotherSensorEntityDescription(
        key="yellow_drum_remaining_life",
        translation_key="yellow_drum_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.yellow_drum_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="yellow_drum_remaining_pages",
        translation_key="yellow_drum_remaining_pages",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.yellow_drum_remaining_pages,
    ),
    BrotherSensorEntityDescription(
        key="yellow_drum_counter",
        translation_key="yellow_drum_page_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.yellow_drum_counter,
    ),
    BrotherSensorEntityDescription(
        key="belt_unit_remaining_life",
        translation_key="belt_unit_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.belt_unit_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="fuser_remaining_life",
        translation_key="fuser_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.fuser_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="laser_remaining_life",
        translation_key="laser_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.laser_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="pf_kit_1_remaining_life",
        translation_key="pf_kit_1_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.pf_kit_1_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="pf_kit_mp_remaining_life",
        translation_key="pf_kit_mp_remaining_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.pf_kit_mp_remaining_life,
    ),
    BrotherSensorEntityDescription(
        key="black_toner_remaining",
        translation_key="black_toner_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.black_toner_remaining,
    ),
    BrotherSensorEntityDescription(
        key="cyan_toner_remaining",
        translation_key="cyan_toner_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.cyan_toner_remaining,
    ),
    BrotherSensorEntityDescription(
        key="magenta_toner_remaining",
        translation_key="magenta_toner_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.magenta_toner_remaining,
    ),
    BrotherSensorEntityDescription(
        key="yellow_toner_remaining",
        translation_key="yellow_toner_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.yellow_toner_remaining,
    ),
    BrotherSensorEntityDescription(
        key="black_ink_remaining",
        translation_key="black_ink_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.black_ink_remaining,
    ),
    BrotherSensorEntityDescription(
        key="cyan_ink_remaining",
        translation_key="cyan_ink_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.cyan_ink_remaining,
    ),
    BrotherSensorEntityDescription(
        key="magenta_ink_remaining",
        translation_key="magenta_ink_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.magenta_ink_remaining,
    ),
    BrotherSensorEntityDescription(
        key="yellow_ink_remaining",
        translation_key="yellow_ink_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.yellow_ink_remaining,
    ),
    BrotherSensorEntityDescription(
        key="uptime",
        translation_key="last_restart",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda data: data.uptime,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrotherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Brother entities from a config_entry."""
    coordinator = entry.runtime_data
    # Due to the change of the attribute name of one sensor, it is necessary to migrate
    # the unique_id to the new one.
    entity_registry = er.async_get(hass)
    old_unique_id = f"{coordinator.brother.serial.lower()}_b/w_counter"
    if entity_id := entity_registry.async_get_entity_id(
        PLATFORM, DOMAIN, old_unique_id
    ):
        new_unique_id = f"{coordinator.brother.serial.lower()}_bw_counter"
        _LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

    async_add_entities(
        BrotherPrinterSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.value(coordinator.data) is not None
    )


class BrotherPrinterSensor(
    CoordinatorEntity[BrotherDataUpdateCoordinator], SensorEntity
):
    """Define an Brother Printer sensor."""

    _attr_has_entity_name = True
    entity_description: BrotherSensorEntityDescription

    def __init__(
        self,
        coordinator: BrotherDataUpdateCoordinator,
        description: BrotherSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.brother.host}/",
            identifiers={(DOMAIN, coordinator.brother.serial)},
            connections={(CONNECTION_NETWORK_MAC, coordinator.brother.mac)},
            serial_number=coordinator.brother.serial,
            manufacturer="Brother",
            model=coordinator.brother.model,
            name=coordinator.brother.model,
            sw_version=coordinator.brother.firmware,
        )
        self._attr_native_value = description.value(coordinator.data)
        self._attr_unique_id = f"{coordinator.brother.serial.lower()}_{description.key}"
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.entity_description.value(self.coordinator.data)
        self.async_write_ha_state()
