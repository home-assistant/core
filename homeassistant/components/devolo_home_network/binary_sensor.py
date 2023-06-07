"""Platform for binary sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from devolo_plc_api import Device
from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONNECTED_PLC_DEVICES, CONNECTED_TO_ROUTER, DOMAIN
from .entity import DevoloEntity


def _is_connected_to_router(entity: DevoloBinarySensorEntity) -> bool:
    """Check, if device is attached to the router."""
    return all(
        device.attached_to_router
        for device in entity.coordinator.data.devices
        if device.mac_address == entity.device.mac
    )


@dataclass
class DevoloBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[DevoloBinarySensorEntity], bool]


@dataclass
class DevoloBinarySensorEntityDescription(
    BinarySensorEntityDescription, DevoloBinarySensorRequiredKeysMixin
):
    """Describes devolo sensor entity."""


SENSOR_TYPES: dict[str, DevoloBinarySensorEntityDescription] = {
    CONNECTED_TO_ROUTER: DevoloBinarySensorEntityDescription(
        key=CONNECTED_TO_ROUTER,
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:router-network",
        value_func=_is_connected_to_router,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinators"]

    entities: list[BinarySensorEntity] = []
    if device.plcnet:
        entities.append(
            DevoloBinarySensorEntity(
                entry,
                coordinators[CONNECTED_PLC_DEVICES],
                SENSOR_TYPES[CONNECTED_TO_ROUTER],
                device,
            )
        )
    async_add_entities(entities)


class DevoloBinarySensorEntity(DevoloEntity[LogicalNetwork], BinarySensorEntity):
    """Representation of a devolo binary sensor."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[LogicalNetwork],
        description: DevoloBinarySensorEntityDescription,
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloBinarySensorEntityDescription = description
        super().__init__(entry, coordinator, device)

    @property
    def is_on(self) -> bool:
        """State of the binary sensor."""
        return self.entity_description.value_func(self)
