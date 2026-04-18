"""Support for MelCloud device binary sensors."""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from typing import Any

from pymelcloud import DEVICE_TYPE_ATW

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator
from .entity import MelCloudEntity


@dataclasses.dataclass(frozen=True, kw_only=True)
class MelcloudBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Melcloud binary sensor entity."""

    value_fn: Callable[[Any], bool | None]
    enabled: Callable[[Any], bool]


ATW_BINARY_SENSORS: tuple[MelcloudBinarySensorEntityDescription, ...] = (
    MelcloudBinarySensorEntityDescription(
        key="boiler_status",
        translation_key="boiler_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.boiler_status,
        enabled=lambda data: data.device.boiler_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="booster_heater1_status",
        translation_key="booster_heater_status",
        translation_placeholders={"number": "1"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.booster_heater1_status,
        enabled=lambda data: data.device.booster_heater1_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="booster_heater2_status",
        translation_key="booster_heater_status",
        translation_placeholders={"number": "2"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.booster_heater2_status,
        enabled=lambda data: data.device.booster_heater2_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="booster_heater2plus_status",
        translation_key="booster_heater_status",
        translation_placeholders={"number": "2+"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.booster_heater2plus_status,
        enabled=lambda data: data.device.booster_heater2plus_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="immersion_heater_status",
        translation_key="immersion_heater_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.immersion_heater_status,
        enabled=lambda data: data.device.immersion_heater_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="water_pump1_status",
        translation_key="water_pump_status",
        translation_placeholders={"number": "1"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.water_pump1_status,
        enabled=lambda data: data.device.water_pump1_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="water_pump2_status",
        translation_key="water_pump_status",
        translation_placeholders={"number": "2"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.water_pump2_status,
        enabled=lambda data: data.device.water_pump2_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="water_pump3_status",
        translation_key="water_pump_status",
        translation_placeholders={"number": "3"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.water_pump3_status,
        enabled=lambda data: data.device.water_pump3_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="water_pump4_status",
        translation_key="water_pump_status",
        translation_placeholders={"number": "4"},
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.water_pump4_status,
        enabled=lambda data: data.device.water_pump4_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="valve_3way_status",
        translation_key="valve_3way_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.device.valve_3way_status,
        enabled=lambda data: data.device.valve_3way_status is not None,
    ),
    MelcloudBinarySensorEntityDescription(
        key="valve_2way_status",
        translation_key="valve_2way_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.device.valve_2way_status,
        enabled=lambda data: data.device.valve_2way_status is not None,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MelCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud device binary sensors based on config_entry."""
    coordinator = entry.runtime_data

    if DEVICE_TYPE_ATW not in coordinator:
        return

    entities: list[MelDeviceBinarySensor] = [
        MelDeviceBinarySensor(coord, description)
        for description in ATW_BINARY_SENSORS
        for coord in coordinator[DEVICE_TYPE_ATW]
        if description.enabled(coord)
    ]
    async_add_entities(entities)


class MelDeviceBinarySensor(MelCloudEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    entity_description: MelcloudBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        description: MelcloudBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.serial}-{coordinator.device.mac}-{description.key}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator)
