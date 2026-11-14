"""Binary sensor platform for the HP Printer integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiohpprinter import HpPrinterData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HpPrinterConfigEntry, HpPrinterDataUpdateCoordinator
from .entity import HpPrinterEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HpPrinterBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an HP Printer binary sensor entity."""

    value_fn: Callable[[HpPrinterData], bool | None]


def _adapter_connected(name: str) -> Callable[[HpPrinterData], bool | None]:
    """Return a function reading whether the named network adapter is connected."""

    def _value(data: HpPrinterData) -> bool | None:
        return next(
            (
                adapter.is_connected
                for adapter in data.adapters
                if adapter.name and adapter.name.lower() == name
            ),
            None,
        )

    return _value


BINARY_SENSORS: tuple[HpPrinterBinarySensorEntityDescription, ...] = (
    HpPrinterBinarySensorEntityDescription(
        key="ethernet",
        translation_key="ethernet",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_adapter_connected("eth0"),
    ),
    HpPrinterBinarySensorEntityDescription(
        key="wifi",
        translation_key="wifi",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_adapter_connected("wifi0"),
    ),
    HpPrinterBinarySensorEntityDescription(
        key="usb",
        translation_key="usb",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_adapter_connected("usb0"),
    ),
    HpPrinterBinarySensorEntityDescription(
        key="cloud_registered",
        translation_key="cloud_registered",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.eprint.is_registered if data.eprint else None,
    ),
    HpPrinterBinarySensorEntityDescription(
        key="cloud_services",
        translation_key="cloud_services",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.eprint.cloud_services_enabled if data.eprint else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HpPrinterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HP Printer binary sensors from a config entry."""
    coordinator = entry.runtime_data
    known_keys: set[str] = set()

    def _check_binary_sensors() -> None:
        new_descriptions = [
            description
            for description in BINARY_SENSORS
            if description.key not in known_keys
            and description.value_fn(coordinator.data) is not None
        ]
        if new_descriptions:
            known_keys.update(description.key for description in new_descriptions)
            async_add_entities(
                HpPrinterBinarySensor(coordinator, description)
                for description in new_descriptions
            )

    _check_binary_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_check_binary_sensors))


class HpPrinterBinarySensor(HpPrinterEntity, BinarySensorEntity):
    """Representation of an HP Printer binary sensor."""

    entity_description: HpPrinterBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HpPrinterDataUpdateCoordinator,
        description: HpPrinterBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
