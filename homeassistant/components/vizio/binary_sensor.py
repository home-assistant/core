"""Binary sensor platform for Vizio SmartCast devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from vizaio import ChargingStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VizioConfigEntry, VizioDeviceCoordinator, VizioDeviceData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VizioBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Vizio binary sensor entity."""

    value_fn: Callable[[VizioDeviceData], bool | None]


BINARY_SENSORS: tuple[VizioBinarySensorEntityDescription, ...] = (
    VizioBinarySensorEntityDescription(
        key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        # A fully charged battery is not drawing charge, so it reports off;
        # the battery level sensor is what tells the user it is full.
        value_fn=lambda data: (
            data.charging_status is ChargingStatus.CHARGING
            if data.charging_status is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vizio binary sensor entities."""
    coordinator = config_entry.runtime_data.device_coordinator
    if not coordinator.device.profile.has_battery:
        return

    async_add_entities(
        VizioBinarySensor(config_entry, coordinator, description)
        for description in BINARY_SENSORS
    )


class VizioBinarySensor(CoordinatorEntity[VizioDeviceCoordinator], BinarySensorEntity):
    """Binary sensor entity for battery-powered Vizio SmartCast devices."""

    _attr_has_entity_name = True
    entity_description: VizioBinarySensorEntityDescription

    def __init__(
        self,
        config_entry: VizioConfigEntry,
        coordinator: VizioDeviceCoordinator,
        description: VizioBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        unique_id = config_entry.unique_id
        # Guard against config entries missing unique_id, which should never happen
        if TYPE_CHECKING:
            assert unique_id is not None
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the battery is charging."""
        return self.entity_description.value_fn(self.coordinator.data)
