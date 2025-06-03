"""Platform for binary sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONNECTED_PLC_DEVICES, CONNECTED_TO_ROUTER
from .coordinator import DevoloDataUpdateCoordinator, DevoloHomeNetworkConfigEntry
from .entity import DevoloCoordinatorEntity

PARALLEL_UPDATES = 0


def _is_connected_to_router(entity: DevoloBinarySensorEntity) -> bool:
    """Check, if device is attached to the router."""
    return all(
        device.attached_to_router
        for device in entity.coordinator.data.devices
        if device.mac_address == entity.device.mac
    )


@dataclass(frozen=True, kw_only=True)
class DevoloBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes devolo sensor entity."""

    value_func: Callable[[DevoloBinarySensorEntity], bool]


SENSOR_TYPES: dict[str, DevoloBinarySensorEntityDescription] = {
    CONNECTED_TO_ROUTER: DevoloBinarySensorEntityDescription(
        key=CONNECTED_TO_ROUTER,
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_func=_is_connected_to_router,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    coordinators = entry.runtime_data.coordinators

    entities: list[BinarySensorEntity] = []
    entities.append(
        DevoloBinarySensorEntity(
            entry,
            coordinators[CONNECTED_PLC_DEVICES],
            SENSOR_TYPES[CONNECTED_TO_ROUTER],
        )
    )
    async_add_entities(entities)


class DevoloBinarySensorEntity(
    DevoloCoordinatorEntity[LogicalNetwork], BinarySensorEntity
):
    """Representation of a devolo binary sensor."""

    def __init__(
        self,
        entry: DevoloHomeNetworkConfigEntry,
        coordinator: DevoloDataUpdateCoordinator[LogicalNetwork],
        description: DevoloBinarySensorEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.entity_description: DevoloBinarySensorEntityDescription = description
        super().__init__(entry, coordinator)

    @property
    def is_on(self) -> bool:
        """State of the binary sensor."""
        return self.entity_description.value_func(self)
