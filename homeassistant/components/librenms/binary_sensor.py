"""Binary sensor platform for the LibreNMS integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import override

from aiolibrenms.devices.models import LibrenmsDeviceInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LibrenmsConfigEntry, LibrenmsDataUpdateCoordinator
from .entity import LibrenmsDeviceEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LibrenmsDeviceBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Librenms device sensor entity description."""

    value: Callable[[LibrenmsDeviceInfo], bool]
    is_suitable: Callable[[LibrenmsDeviceInfo], bool] = lambda _: True


DEVICE_SENSOR_TYPES: tuple[LibrenmsDeviceBinarySensorEntityDescription, ...] = (
    LibrenmsDeviceBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value=lambda data: data.status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LibrenmsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add LibreNMS server state sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        LibrenmsDeviceBinarySensorEntity(coordinator, description, dev_info)
        for description in DEVICE_SENSOR_TYPES
        for dev_info in coordinator.data.devices
        if description.is_suitable(dev_info)
    )


class LibrenmsDeviceBinarySensorEntity(LibrenmsDeviceEntity, BinarySensorEntity):
    """Define Librenms sensor entity."""

    entity_description: LibrenmsDeviceBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LibrenmsDataUpdateCoordinator,
        description: LibrenmsDeviceBinarySensorEntityDescription,
        dev_info: LibrenmsDeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, dev_info)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{dev_info.device_id}_{description.key}"
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self.dev_info)
