"""Binary sensor platform for Nest devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.models import (
    NestDevice,
    NestLock,
    NestProtect,
    NestThermostat,
    NestWiredProtect,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NestBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to describe a Nest binary sensor."""

    value_fn: Callable[[Any], bool]
    device_types: tuple[type[NestDevice], ...]
    unavailable_on_protobuf: bool = False


_DESCRIPTIONS: tuple[NestBinarySensorEntityDescription, ...] = (
    # Protect sensors
    # Core Safety
    NestBinarySensorEntityDescription(
        key="smoke_status",
        translation_key="smoke_status",
        device_class=BinarySensorDeviceClass.SMOKE,
        value_fn=lambda device: device.smoke_status,
        device_types=(NestProtect,),
    ),
    NestBinarySensorEntityDescription(
        key="co_status",
        translation_key="co_status",
        device_class=BinarySensorDeviceClass.CO,
        value_fn=lambda device: device.co_status,
        device_types=(NestProtect,),
    ),
    NestBinarySensorEntityDescription(
        key="heat_status",
        translation_key="heat_status",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda device: device.heat_status,
        device_types=(NestProtect,),
        unavailable_on_protobuf=True,  # No Protobuf trait available
    ),
    # Diagnostics
    NestBinarySensorEntityDescription(
        key="battery_health_state",
        translation_key="battery_health",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery_health_state != 0,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    # Component Tests
    NestBinarySensorEntityDescription(
        key="component_speaker_test_passed",
        translation_key="speaker_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:speaker-wireless",
        value_fn=lambda device: not device.component_speaker_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_smoke_test_passed",
        translation_key="smoke_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:smoke",
        value_fn=lambda device: not device.component_smoke_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_co_test_passed",
        translation_key="co_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:molecule-co",
        value_fn=lambda device: not device.component_co_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_wifi_test_passed",
        translation_key="wifi_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi",
        value_fn=lambda device: not device.component_wifi_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_led_test_passed",
        translation_key="led_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:led-off",
        value_fn=lambda device: not device.component_led_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_pir_test_passed",
        translation_key="pir_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:run",
        value_fn=lambda device: not device.component_pir_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_buzzer_test_passed",
        translation_key="buzzer_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alarm-bell",
        value_fn=lambda device: not device.component_buzzer_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="component_hum_test_passed",
        translation_key="humidity_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:water-percent",
        value_fn=lambda device: not device.component_hum_test_passed,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
    ),
    NestBinarySensorEntityDescription(
        key="removed_from_base",
        translation_key="removed_from_base",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:tray-remove",
        value_fn=lambda device: device.removed_from_base,
        device_types=(NestProtect,),
        entity_registry_enabled_default=False,
        unavailable_on_protobuf=True,  # No Protobuf trait available
    ),
    # Wired specific
    NestBinarySensorEntityDescription(
        key="line_power_present",
        translation_key="line_power",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.line_power_present,
        device_types=(NestWiredProtect,),
    ),
    NestBinarySensorEntityDescription(
        key="occupancy",
        translation_key="occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        value_fn=lambda device: device.occupancy,
        device_types=(
            NestWiredProtect,
            NestThermostat,
        ),
    ),
    # Thermostat sensors
    NestBinarySensorEntityDescription(
        key="leaf",
        translation_key="eco_mode",
        icon="mdi:leaf",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.leaf,
        device_types=(NestThermostat,),
    ),
    NestBinarySensorEntityDescription(
        key="filter_replacement_needed",
        translation_key="filter_replacement_needed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.filter_replacement_needed is True,
        device_types=(NestThermostat,),
    ),
    # Lock sensors
    NestBinarySensorEntityDescription(
        key="tampered",
        translation_key="tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.tampered,
        device_types=(NestLock,),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest binary sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[NestBinarySensor] = []

    for device in coordinator.data.values():
        for description in _DESCRIPTIONS:
            if not isinstance(device, description.device_types):
                continue
            if description.unavailable_on_protobuf and device.is_protobuf:
                continue
            if getattr(device, description.key, None) is not None:
                entities.append(NestBinarySensor(coordinator, device, description))

    async_add_entities(entities)


class NestBinarySensor(NestEntity[NestDevice], BinarySensorEntity):
    """Representation of a Nest Binary Sensor."""

    entity_description: NestBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestDevice,
        description: NestBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.serial_number}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)
