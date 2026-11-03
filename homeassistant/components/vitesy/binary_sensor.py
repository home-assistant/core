"""Binary sensor platform for the Vitesy integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiovitesy.api import VitesyDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import VitesyConfigEntry, VitesyDataUpdateCoordinator
from .entity import VitesyEntity

PARALLEL_UPDATES = 0


def _status_flag(reading_id: str) -> Callable[[VitesyDevice], bool | None]:
    """Return a value function for a boolean status_data reading."""

    def _value(device: VitesyDevice) -> bool | None:
        for entry in device.measurement.get("status_data", ()):
            if entry.get("id") == reading_id:
                value = entry.get("value")
                if isinstance(value, bool):
                    return value
                LOGGER.warning(
                    "Ignoring non-boolean value for reading %s on %s: %r",
                    reading_id,
                    device.name,
                    value,
                )
                return None
        return None

    return _value


@dataclass(frozen=True, kw_only=True)
class VitesyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Vitesy binary sensor entity."""

    value_fn: Callable[[VitesyDevice], bool | None]


BINARY_SENSORS: tuple[VitesyBinarySensorEntityDescription, ...] = (
    VitesyBinarySensorEntityDescription(
        key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_status_flag("charging"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitesyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitesy binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        VitesyBinarySensor(coordinator, device_id, description)
        for device_id, device in coordinator.data.items()
        for description in BINARY_SENSORS
        if description.value_fn(device) is not None
    )


class VitesyBinarySensor(VitesyEntity, BinarySensorEntity):
    """Representation of a Vitesy binary sensor."""

    entity_description: VitesyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: VitesyDataUpdateCoordinator,
        device_id: str,
        description: VitesyBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when the device reports the condition as active."""
        return self.entity_description.value_fn(self.device)
