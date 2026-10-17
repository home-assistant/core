"""Sensor platform for the HP Printer integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiohpprinter import HpConsumable, HpPrinterData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import LOGGER
from .coordinator import HpPrinterConfigEntry, HpPrinterDataUpdateCoordinator
from .entity import HpPrinterEntity

PARALLEL_UPDATES = 0

# Status categories reported by the printer, mapped to a translatable state.
DEVICE_STATUSES = {
    "canceljob": "cancel_job",
    "copying": "copying",
    "inpowersave": "in_power_save",
    "off": "off",
    "processing": "processing",
    "ready": "ready",
    "scanprocessing": "scan_processing",
    "trayempty": "tray_empty",
}

# Consumable label codes reported by the printer, mapped to a translatable name.
CONSUMABLE_COLORS = {
    "C": "cyan",
    "M": "magenta",
    "Y": "yellow",
    "K": "black",
    "CMY": "tri_color",
}


def _device_status(data: HpPrinterData) -> str | None:
    """Return the device status, if it is one of the known statuses."""
    if data.status is None or data.status.device_status is None:
        return None
    if (status := data.status.device_status) not in DEVICE_STATUSES:
        LOGGER.debug("Unknown device status: %s", status)
        return None
    return DEVICE_STATUSES[status]


@dataclass(frozen=True, kw_only=True)
class HpPrinterSensorEntityDescription(SensorEntityDescription):
    """Describes an HP Printer sensor entity."""

    value_fn: Callable[[HpPrinterData], StateType]
    always_create: bool = False


@dataclass(frozen=True, kw_only=True)
class HpPrinterConsumableSensorEntityDescription(SensorEntityDescription):
    """Describes an HP Printer consumable sensor entity."""

    value_fn: Callable[[HpConsumable], StateType]


SENSORS: tuple[HpPrinterSensorEntityDescription, ...] = (
    HpPrinterSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(DEVICE_STATUSES.values()),
        # Unknown statuses are reported as None, which must not hide the sensor.
        always_create=True,
        value_fn=_device_status,
    ),
    HpPrinterSensorEntityDescription(
        key="total_pages",
        translation_key="total_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.printer_usage.total_impressions if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="monochrome_pages",
        translation_key="monochrome_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.printer_usage.monochrome_impressions if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="color_pages",
        translation_key="color_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.printer_usage.color_impressions if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="simplex_sheets",
        translation_key="simplex_sheets",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.printer_usage.simplex_sheets if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="duplex_sheets",
        translation_key="duplex_sheets",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.printer_usage.duplex_sheets if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="jams",
        translation_key="jams",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.printer_usage.jam_events if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="mispicks",
        translation_key="mispicks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.printer_usage.mispick_events if data.printer_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="scanned_pages",
        translation_key="scanned_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.scanner_usage.scan_images if data.scanner_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="scanned_adf_pages",
        translation_key="scanned_adf_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.scanner_usage.adf_images if data.scanner_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="scanned_flatbed_pages",
        translation_key="scanned_flatbed_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.scanner_usage.flatbed_images if data.scanner_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="scanned_duplex_sheets",
        translation_key="scanned_duplex_sheets",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.scanner_usage.duplex_sheets if data.scanner_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="scanner_jams",
        translation_key="scanner_jams",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.scanner_usage.jam_events if data.scanner_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="scanner_mispicks",
        translation_key="scanner_mispicks",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.scanner_usage.mispick_events if data.scanner_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="copied_pages",
        translation_key="copied_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.copy_usage.total_impressions if data.copy_usage else None
        ),
    ),
    HpPrinterSensorEntityDescription(
        key="faxed_pages",
        translation_key="faxed_pages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.fax_usage.total_impressions if data.fax_usage else None
        ),
    ),
)

CONSUMABLE_SENSORS: tuple[HpPrinterConsumableSensorEntityDescription, ...] = (
    HpPrinterConsumableSensorEntityDescription(
        key="level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda consumable: consumable.percentage_level_remaining,
    ),
    HpPrinterConsumableSensorEntityDescription(
        key="pages_remaining",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda consumable: consumable.estimated_pages_remaining,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HpPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HP Printer sensors from a config entry."""

    coordinator = entry.runtime_data

    # Never forgotten: a consumable sensor stays (unavailable) while its
    # cartridge is out, so re-adding it would duplicate its unique ID.
    known_sensors: set[str] = set()

    def _check_sensors() -> None:
        data = coordinator.data
        current_sensors = {
            description.key
            for description in SENSORS
            if description.always_create or description.value_fn(data) is not None
        } | {
            f"{consumable.consumable_id}_{description.key}"
            for consumable in data.consumables
            if consumable.consumable_id in CONSUMABLE_COLORS
            for description in CONSUMABLE_SENSORS
            if description.value_fn(consumable) is not None
        }
        new_sensors = current_sensors - known_sensors
        if new_sensors:
            known_sensors.update(new_sensors)
            sensors_list: list[SensorEntity] = [
                HpPrinterSensor(coordinator, sensor_desc)
                for sensor_desc in SENSORS
                if sensor_desc.key in new_sensors
            ]
            consumables_list: list[SensorEntity] = [
                HpPrinterConsumableSensor(
                    coordinator, consumable.consumable_id, consumable_desc
                )
                for consumable in data.consumables
                for consumable_desc in CONSUMABLE_SENSORS
                if f"{consumable.consumable_id}_{consumable_desc.key}" in new_sensors
            ]
            async_add_entities(sensors_list + consumables_list)

    _check_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_check_sensors))


class HpPrinterSensor(HpPrinterEntity, SensorEntity):
    """Representation of an HP Printer sensor."""

    entity_description: HpPrinterSensorEntityDescription

    def __init__(
        self,
        coordinator: HpPrinterDataUpdateCoordinator,
        description: HpPrinterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class HpPrinterConsumableSensor(HpPrinterEntity, SensorEntity):
    """Representation of a sensor for a single ink or toner consumable."""

    entity_description: HpPrinterConsumableSensorEntityDescription

    def __init__(
        self,
        coordinator: HpPrinterDataUpdateCoordinator,
        consumable_id: str,
        description: HpPrinterConsumableSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._consumable_id = consumable_id
        self._attr_translation_key = (
            f"{CONSUMABLE_COLORS[consumable_id]}_{description.key}"
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{consumable_id}_{description.key}"
        )

        self._update_from_consumable()

    def _update_from_consumable(self) -> None:
        """Read this entity's consumable from the latest coordinator data."""
        consumable = next(
            (
                consumable
                for consumable in self.coordinator.data.consumables
                if consumable.consumable_id == self._consumable_id
            ),
            None,
        )
        self._consumable_reported = consumable is not None
        if consumable is not None:
            self._attr_native_value = self.entity_description.value_fn(consumable)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_consumable()
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return True when the consumable is still reported by the printer."""
        return super().available and self._consumable_reported
