"""Plugwise Binary Sensor component for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity

SEVERITIES = ["other", "info", "warning", "error"]


@dataclass
class PlugwiseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Plugwise binary sensor entity."""

    icon_off: str | None = None


BINARY_SENSORS: tuple[PlugwiseBinarySensorEntityDescription, ...] = (
    PlugwiseBinarySensorEntityDescription(
        key="dhw_state",
        name="DHW State",
        icon="mdi:water-pump",
        icon_off="mdi:water-pump-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="slave_boiler_state",
        name="Secondary Boiler State",
        icon="mdi:fire",
        icon_off="mdi:circle-off-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PlugwiseBinarySensorEntityDescription(
        key="plugwise_notification",
        name="Plugwise Notification",
        icon="mdi:mailbox-up-outline",
        icon_off="mdi:mailbox-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        for description in BINARY_SENSORS:
            if (
                "binary_sensors" not in device
                or description.key not in device["binary_sensors"]
            ):
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
        self._attr_name = (
            f"{coordinator.data.devices[device_id].get('name', '')} {description.name}"
        ).lstrip()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not (data := self.coordinator.data.devices.get(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._dev_id)
            super()._handle_coordinator_update()
            return

        state = data["binary_sensors"].get(self.entity_description.key)
        self._attr_is_on = state
        if icon_off := self.entity_description.icon_off:
            self._attr_icon = self.entity_description.icon if state else icon_off

        # Add entity attribute for Plugwise notifications
        if self.entity_description.key == "plugwise_notification":
            self._attr_extra_state_attributes = {
                f"{severity}_msg": [] for severity in SEVERITIES
            }

            if notify := self.coordinator.data.gateway["notifications"]:
                for details in notify.values():
                    for msg_type, msg in details.items():
                        msg_type = msg_type.lower()
                        if msg_type not in SEVERITIES:
                            msg_type = "other"
                        self._attr_extra_state_attributes[f"{msg_type}_msg"].append(msg)

        super()._handle_coordinator_update()
