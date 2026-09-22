"""Support for the Brother binary sensors."""

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BrotherConfigEntry
from .entity import BrotherPrinterEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

# The printer's `offline` error is not exposed here, the `status` sensor already
# reports printer reachability.
PRINTER_ERRORS = (
    "door_open",
    "input_tray_empty",
    "input_tray_missing",
    "jammed",
    "low_paper",
    "low_toner",
    "marker_supply_missing",
    "no_paper",
    "no_toner",
    "output_full",
    "output_near_full",
    "output_tray_missing",
    "overdue_prevent_maint",
    "service_requested",
)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = tuple(
    BinarySensorEntityDescription(
        key=error,
        translation_key=error,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    for error in PRINTER_ERRORS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BrotherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Brother entities from a config_entry."""
    coordinator = entry.runtime_data

    if coordinator.data.printer_errors is None:
        return

    async_add_entities(
        BrotherPrinterBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
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
