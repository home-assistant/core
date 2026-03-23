"""Binary sensor platform for Indevolt integration."""

from dataclasses import dataclass, field
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator
from .entity import IndevoltEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndevoltBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Custom entity description class for Indevolt binary sensors."""

    on_value: int = 1
    generation: list[int] = field(default_factory=lambda: [1, 2])


BINARY_SENSORS: Final = (
    # Electricity Meter Status
    IndevoltBinarySensorEntityDescription(
        key="7120",
        translation_key="meter_connected",
        on_value=1000,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Electric Heating State
    IndevoltBinarySensorEntityDescription(
        key="9079",
        generation=[2],
        translation_key="main_electric_heating_state",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key="9096",
        generation=[2],
        translation_key="battery_pack_1_electric_heating_state",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key="9112",
        generation=[2],
        translation_key="battery_pack_2_electric_heating_state",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key="9128",
        generation=[2],
        translation_key="battery_pack_3_electric_heating_state",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key="9144",
        generation=[2],
        translation_key="battery_pack_4_electric_heating_state",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key="9279",
        generation=[2],
        translation_key="battery_pack_5_electric_heating_state",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# Sensors per battery pack  (SN, heating state)
BATTERY_PACK_SENSOR_KEYS = [
    ("9032", "9096"),  # Battery Pack 1
    ("9051", "9112"),  # Battery Pack 2
    ("9070", "9128"),  # Battery Pack 3
    ("9165", "9144"),  # Battery Pack 4
    ("9218", "9279"),  # Battery Pack 5
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = coordinator.generation

    excluded_keys: set[str] = set()
    for pack_keys in BATTERY_PACK_SENSOR_KEYS:
        sn_key = pack_keys[0]

        if not coordinator.data.get(sn_key):
            excluded_keys.update(pack_keys)

    async_add_entities(
        IndevoltBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
        if device_gen in description.generation and description.key not in excluded_keys
    )


class IndevoltBinarySensorEntity(IndevoltEntity, BinarySensorEntity):
    """Represents a binary sensor entity for Indevolt devices."""

    entity_description: IndevoltBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: IndevoltCoordinator,
        description: IndevoltBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Indevolt binary sensor entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return on/active state of the binary sensor."""
        raw_value = self.coordinator.data.get(self.entity_description.key)
        if raw_value is None:
            return None

        return raw_value == self.entity_description.on_value
