"""Binary sensor platform for Indevolt integration."""

from dataclasses import dataclass
from typing import Final

from indevolt_api import IndevoltBattery, IndevoltGrid, IndevoltSystem

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
    off_value: int = 0
    generation: tuple[int, ...] = (1, 2)


BINARY_SENSORS: Final = (
    # Electricity Meter Status
    IndevoltBinarySensorEntityDescription(
        key=IndevoltGrid.METER_CONNECTED,
        translation_key="meter_connected",
        on_value=1000,
        off_value=1001,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Electric Heating States
    IndevoltBinarySensorEntityDescription(
        key=IndevoltSystem.HEATING_STATE,
        generation=(1,),
        translation_key="electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key=IndevoltBattery.MAIN_HEATING_STATE,
        generation=(2,),
        translation_key="main_electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key=IndevoltBattery.PACK_1_HEATING_STATE,
        generation=(2,),
        translation_key="battery_pack_1_electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key=IndevoltBattery.PACK_2_HEATING_STATE,
        generation=(2,),
        translation_key="battery_pack_2_electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key=IndevoltBattery.PACK_3_HEATING_STATE,
        generation=(2,),
        translation_key="battery_pack_3_electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key=IndevoltBattery.PACK_4_HEATING_STATE,
        generation=(2,),
        translation_key="battery_pack_4_electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    IndevoltBinarySensorEntityDescription(
        key=IndevoltBattery.PACK_5_HEATING_STATE,
        generation=(2,),
        translation_key="battery_pack_5_electric_heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# Sensor per battery pack: (serial_number_key, heating_state_key)
BATTERY_PACK_SENSOR_KEYS = [
    (IndevoltBattery.PACK_1_SERIAL_NUMBER, IndevoltBattery.PACK_1_HEATING_STATE),
    (IndevoltBattery.PACK_2_SERIAL_NUMBER, IndevoltBattery.PACK_2_HEATING_STATE),
    (IndevoltBattery.PACK_3_SERIAL_NUMBER, IndevoltBattery.PACK_3_HEATING_STATE),
    (IndevoltBattery.PACK_4_SERIAL_NUMBER, IndevoltBattery.PACK_4_HEATING_STATE),
    (IndevoltBattery.PACK_5_SERIAL_NUMBER, IndevoltBattery.PACK_5_HEATING_STATE),
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
    for sn_key, heating_key in BATTERY_PACK_SENSOR_KEYS:
        if not coordinator.data.get(sn_key):
            excluded_keys.add(heating_key)

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

        if raw_value == self.entity_description.on_value:
            return True

        if raw_value == self.entity_description.off_value:
            return False

        return None
