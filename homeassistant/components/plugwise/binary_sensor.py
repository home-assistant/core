"""Plugwise Binary Sensor component for Home Assistant."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from plugwise.constants import BinarySensorType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugwiseConfigEntry
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity

SEVERITIES = ["other", "info", "warning", "error"]


@dataclass(frozen=True)
class PlugwiseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Plugwise binary sensor entity."""

    key: BinarySensorType


BINARY_SENSORS: tuple[PlugwiseBinarySensorEntityDescription, ...] = (
    PlugwiseBinarySensorEntityDescription(
        key="low_battery",
        translation_key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="compressor_state",
        translation_key="compressor_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="cooling_enabled",
        translation_key="cooling_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="dhw_state",
        translation_key="dhw_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="flame_state",
        translation_key="flame_state",
        name="Flame state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="heating_state",
        translation_key="heating_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="cooling_state",
        translation_key="cooling_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="secondary_boiler_state",
        translation_key="secondary_boiler_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="plugwise_notification",
        translation_key="plugwise_notification",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile binary_sensors from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseBinarySensorEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            if (
                binary_sensors := coordinator.data.devices[device_id].get(
                    "binary_sensors"
                )
            )
            for description in BINARY_SENSORS
            if description.key in binary_sensors
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseBinarySensorEntity(PlugwiseEntity, BinarySensorEntity):
    """Represent Smile Binary Sensors."""

    entity_description: PlugwiseBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseBinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary_sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.device["binary_sensors"][self.entity_description.key]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        if self.entity_description.key != "plugwise_notification":
            return None

        attrs: dict[str, list[str]] = {f"{severity}_msg": [] for severity in SEVERITIES}
        if notify := self.coordinator.data.gateway["notifications"]:
            for details in notify.values():
                for msg_type, msg in details.items():
                    msg_type = msg_type.lower()
                    if msg_type not in SEVERITIES:
                        msg_type = "other"
                    attrs[f"{msg_type}_msg"].append(msg)

        return attrs
