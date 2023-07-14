"""Plugwise Binary Sensor component for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from plugwise import SmileBinarySensors

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity

SEVERITIES = ["other", "info", "warning", "error"]


@dataclass
class PlugwiseBinarySensorMixin:
    """Mixin for required Plugwise binary sensor base description keys."""

    value_fn: Callable[[SmileBinarySensors], bool]


@dataclass
class PlugwiseBinarySensorEntityDescription(
    BinarySensorEntityDescription, PlugwiseBinarySensorMixin
):
    """Describes a Plugwise binary sensor entity."""

    icon_off: str | None = None


BINARY_SENSORS: tuple[PlugwiseBinarySensorEntityDescription, ...] = (
    PlugwiseBinarySensorEntityDescription(
        key="compressor_state",
        translation_key="compressor_state",
        icon="mdi:hvac",
        icon_off="mdi:hvac-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["compressor_state"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="cooling_enabled",
        translation_key="cooling_enabled",
        icon="mdi:snowflake-thermometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["cooling_enabled"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="dhw_state",
        translation_key="dhw_state",
        icon="mdi:water-pump",
        icon_off="mdi:water-pump-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["dhw_state"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="flame_state",
        translation_key="flame_state",
        name="Flame state",
        icon="mdi:fire",
        icon_off="mdi:fire-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["flame_state"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="heating_state",
        translation_key="heating_state",
        icon="mdi:radiator",
        icon_off="mdi:radiator-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["heating_state"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="cooling_state",
        translation_key="cooling_state",
        icon="mdi:snowflake",
        icon_off="mdi:snowflake-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["cooling_state"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="slave_boiler_state",
        translation_key="slave_boiler_state",
        icon="mdi:fire",
        icon_off="mdi:circle-off-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["slave_boiler_state"],
    ),
    PlugwiseBinarySensorEntityDescription(
        key="plugwise_notification",
        translation_key="plugwise_notification",
        icon="mdi:mailbox-up-outline",
        icon_off="mdi:mailbox-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data["plugwise_notification"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile binary_sensors from a config entry."""
    coordinator: PlugwiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[PlugwiseBinarySensorEntity] = []
    for device_id, device in coordinator.data.devices.items():
        if not (binary_sensors := device.get("binary_sensors")):
            continue
        for description in BINARY_SENSORS:
            if description.key not in binary_sensors:
                continue

            entities.append(
                PlugwiseBinarySensorEntity(
                    coordinator,
                    device_id,
                    description,
                )
            )
    async_add_entities(entities)


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
        return self.entity_description.value_fn(self.device["binary_sensors"])

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon_off := self.entity_description.icon_off) and self.is_on is False:
            return icon_off
        return self.entity_description.icon

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
