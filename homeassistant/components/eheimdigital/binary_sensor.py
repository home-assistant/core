"""EHEIM Digital binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from eheimdigital.device import EheimDigitalDevice
from eheimdigital.reeflex import EheimDigitalReeflexUV

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EheimDigitalBinarySensorDescription[_DeviceT: EheimDigitalDevice](
    BinarySensorEntityDescription
):
    """Class describing EHEIM Digital binary sensor entities."""

    value_fn: Callable[[_DeviceT], bool | None]


REEFLEX_DESCRIPTIONS: tuple[
    EheimDigitalBinarySensorDescription[EheimDigitalReeflexUV], ...
] = (
    EheimDigitalBinarySensorDescription[EheimDigitalReeflexUV](
        key="is_lighting",
        translation_key="is_lighting",
        value_fn=lambda device: device.is_lighting,
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    EheimDigitalBinarySensorDescription[EheimDigitalReeflexUV](
        key="is_uvc_connected",
        translation_key="is_uvc_connected",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.is_uvc_connected,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so binary sensors can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the binary sensor entities for one or multiple devices."""
        entities: list[EheimDigitalBinarySensor[Any]] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalReeflexUV):
                entities += [
                    EheimDigitalBinarySensor[EheimDigitalReeflexUV](
                        coordinator, device, description
                    )
                    for description in REEFLEX_DESCRIPTIONS
                ]

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalBinarySensor[_DeviceT: EheimDigitalDevice](
    EheimDigitalEntity[_DeviceT], BinarySensorEntity
):
    """Represent an EHEIM Digital binary sensor entity."""

    entity_description: EheimDigitalBinarySensorDescription[_DeviceT]

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT,
        description: EheimDigitalBinarySensorDescription[_DeviceT],
    ) -> None:
        """Initialize an EHEIM Digital binary sensor entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    def _async_update_attrs(self) -> None:
        self._attr_is_on = self.entity_description.value_fn(self._device)
