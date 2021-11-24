"""Platform for binary sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from devolo_plc_api.device import Device

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PLUG,
    DEVICE_CLASS_UPDATE,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_TO_ROUTER,
    DOMAIN,
    FIRMWARE_UPDATE_AVAILABLE,
)
from .entity import DevoloEntity


@dataclass
class DevoloBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[dict[str, Any]], bool]


@dataclass
class DevoloBinarySensorEntityDescription(
    BinarySensorEntityDescription, DevoloBinarySensorRequiredKeysMixin
):
    """Describes devolo sensor entity."""


SENSOR_TYPES: dict[str, DevoloBinarySensorEntityDescription] = {
    FIRMWARE_UPDATE_AVAILABLE: DevoloBinarySensorEntityDescription(
        key=FIRMWARE_UPDATE_AVAILABLE,
        device_class=DEVICE_CLASS_UPDATE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=True,
        icon="mdi:update",
        name="Firmware update available",
        value_func=lambda data: data["result"] == "UPDATE_AVAILABLE",  # type: ignore[no-any-return]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id][
        "coordinators"
    ]

    entities: list[BinarySensorEntity] = []
    if device.device and "update" in device.device.features:
        entities.append(
            DevoloBinarySensorEntity(
                coordinators[FIRMWARE_UPDATE_AVAILABLE],
                SENSOR_TYPES[FIRMWARE_UPDATE_AVAILABLE],
                device,
                entry.title,
            )
        )
    if device.plcnet:
        entities.append(
            DevoloAttachedToRouterEntity(
                coordinators[CONNECTED_PLC_DEVICES],
                device,
                entry.title,
            )
        )
    async_add_entities(entities)


class DevoloBinarySensorEntity(DevoloEntity, BinarySensorEntity):
    """Representation of a devolo binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: DevoloBinarySensorEntityDescription,
        device: Device,
        device_name: str,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloBinarySensorEntityDescription = description
        super().__init__(coordinator, device, device_name)

    @property
    def is_on(self) -> bool:
        """State of the binary sensor."""
        return self.entity_description.value_func(self.coordinator.data)


class DevoloAttachedToRouterEntity(DevoloEntity, BinarySensorEntity):
    """Representation of a special devolo binary sensor. It is special, because the current value cannot be extracted from coordinator data only."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: Device,
        device_name: str,
    ) -> None:
        """Initialize entity."""
        self.entity_description = BinarySensorEntityDescription(
            key=CONNECTED_TO_ROUTER,
            device_class=DEVICE_CLASS_PLUG,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
            entity_registry_enabled_default=False,
            icon="mdi:router-network",
            name="Connected to router",
        )
        super().__init__(coordinator, device, device_name)

    @property
    def is_on(self) -> bool:
        """State of the binary sensor."""
        return all(
            d["attached_to_router"]
            for d in self.coordinator.data["network"]["devices"]
            if d["mac_address"] == self._device.mac
        )
