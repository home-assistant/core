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

from .const import DOMAIN, LOGGER, NO_NOTIFICATION_ICON, NOTIFICATION_ICON
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
        if device["class"] == "heater_central":
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

        if device["class"] == "gateway":
            entities.append(
                PlugwiseNotifyBinarySensorEntity(
                    coordinator,
                    device_id,
                    PlugwiseBinarySensorEntityDescription(
                        key="plugwise_notification",
                        name="Plugwise Notification",
                    ),
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

        super()._handle_coordinator_update()


class PlugwiseNotifyBinarySensorEntity(PlugwiseBinarySensorEntity):
    """Representation of a Plugwise Notification binary_sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        notify = self.coordinator.data.gateway["notifications"]

        self._attr_extra_state_attributes = {}
        for severity in SEVERITIES:
            self._attr_extra_state_attributes[f"{severity}_msg"] = []

        self._attr_is_on = False
        self._attr_icon = NO_NOTIFICATION_ICON

        if notify:
            self._attr_is_on = True
            self._attr_icon = NOTIFICATION_ICON

            for details in notify.values():
                for msg_type, msg in details.items():
                    if msg_type not in SEVERITIES:
                        msg_type = "other"

                    self._attr_extra_state_attributes[f"{msg_type.lower()}_msg"].append(
                        msg
                    )

        self.async_write_ha_state()
