"""Binary sensor platform for AriaQ."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from flow_it_api.models import MachineStatusResponse

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AriaQConfigEntry
from .entity import AriaQVmcEntity


@dataclass(frozen=True, kw_only=True)
class AriaQVmcBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes AriaQ binary sensor entity."""

    value_fn: Callable[[MachineStatusResponse], bool | None]


BINARY_SENSORS: tuple[AriaQVmcBinarySensorEntityDescription, ...] = (
    AriaQVmcBinarySensorEntityDescription(
        key="bypass_on",
        translation_key="bypass_on",
        value_fn=lambda data: data.data.mode.bypassOn,
    ),
    AriaQVmcBinarySensorEntityDescription(
        key="condensation",
        translation_key="condensation",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.condensation,
    ),
    AriaQVmcBinarySensorEntityDescription(
        key="ice",
        translation_key="ice",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.ice,
    ),
    AriaQVmcBinarySensorEntityDescription(
        key="service",
        translation_key="service",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.service,
    ),
    AriaQVmcBinarySensorEntityDescription(
        key="update_reboot",
        translation_key="update_reboot",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.update_reboot,
    ),
    AriaQVmcBinarySensorEntityDescription(
        key="warmup",
        translation_key="warmup",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.data.alert.warmup,
    ),
    AriaQVmcBinarySensorEntityDescription(
        key="worries",
        translation_key="worries",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.alert.worries,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AriaQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AriaQ binary sensors."""
    data = config_entry.runtime_data
    async_add_entities(
        AriaQVmcBinarySensor(data.coordinator, data.vmc, description)
        for description in BINARY_SENSORS
    )


class AriaQVmcBinarySensor(AriaQVmcEntity, BinarySensorEntity):
    """AriaQ binary sensor entity."""

    entity_description: AriaQVmcBinarySensorEntityDescription

    @override
    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data.state)
