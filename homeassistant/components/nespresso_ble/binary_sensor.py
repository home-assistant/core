"""Binary sensor platform for the Nespresso Vertuo integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from nespresso_ble import VMiniDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NespressoBLEConfigEntry, NespressoBLECoordinator
from .entity import NespressoBLEEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NespressoBLEBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Nespresso Vertuo binary sensor entity."""

    value_fn: Callable[[VMiniDevice], bool | None]


BINARY_SENSORS: tuple[NespressoBLEBinarySensorEntityDescription, ...] = (
    NespressoBLEBinarySensorEntityDescription(
        key="descaling_alert",
        translation_key="descaling_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: _as_bool(device.sensors.get("descalingAlert")),
    ),
    NespressoBLEBinarySensorEntityDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: _error_present(device.sensors.get("errorCode")),
    ),
)


def _as_bool(value: str | int | bool | None) -> bool | None:
    """Return a bool value or None."""
    if value is None:
        return None
    return bool(value)


def _error_present(value: str | int | bool | None) -> bool | None:
    """Return True when an error code other than 'no error' is present."""
    if value is None:
        return None
    return str(value).lower() != "no error"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NespressoBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nespresso Vertuo binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        NespressoBLEBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class NespressoBLEBinarySensor(NespressoBLEEntity, BinarySensorEntity):
    """A Nespresso Vertuo binary sensor."""

    entity_description: NespressoBLEBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NespressoBLECoordinator,
        description: NespressoBLEBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.address}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
