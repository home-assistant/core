"""Support for the Brother binary sensors."""

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PRINTER_TYPE_INK, PRINTER_TYPE_LASER
from .coordinator import BrotherConfigEntry
from .entity import BrotherPrinterEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="door_open",
        translation_key="door_open",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="input_tray_empty",
        translation_key="input_tray_empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="input_tray_missing",
        translation_key="input_tray_missing",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="jammed",
        translation_key="jammed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="low_paper",
        translation_key="low_paper",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="no_paper",
        translation_key="no_paper",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="output_full",
        translation_key="output_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="output_near_full",
        translation_key="output_near_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="output_tray_missing",
        translation_key="output_tray_missing",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="overdue_prevent_maint",
        translation_key="overdue_prevent_maint",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="service_requested",
        translation_key="service_requested",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

SUPPLY_BINARY_SENSOR_TYPES: dict[str, tuple[BinarySensorEntityDescription, ...]] = {
    PRINTER_TYPE_LASER: (
        BinarySensorEntityDescription(
            key="low_toner",
            translation_key="low_toner",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        BinarySensorEntityDescription(
            key="no_toner",
            translation_key="no_toner",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    PRINTER_TYPE_INK: (
        BinarySensorEntityDescription(
            key="low_toner",
            translation_key="low_ink",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        BinarySensorEntityDescription(
            key="no_toner",
            translation_key="no_ink",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrotherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Brother entities from a config_entry."""
    coordinator = entry.runtime_data

    # printer_errors is None only if the printer does not support the OID that returns
    # errors, in that case, we do not create binary sensors
    if coordinator.data.printer_errors is None:
        return

    descriptions = (
        BINARY_SENSOR_TYPES + SUPPLY_BINARY_SENSOR_TYPES[entry.data[CONF_TYPE]]
    )

    async_add_entities(
        BrotherPrinterBinarySensor(coordinator, description)
        for description in descriptions
    )


class BrotherPrinterBinarySensor(BrotherPrinterEntity, BinarySensorEntity):
    """Define a Brother Printer binary sensor."""

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the printer reports this error."""
        if TYPE_CHECKING:
            assert self.coordinator.data.printer_errors is not None

        return self.entity_description.key in self.coordinator.data.printer_errors
