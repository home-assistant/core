"""Binary sensor platform for Zinvolt integration."""

from collections.abc import Callable
from dataclasses import dataclass

from zinvolt.models import BatteryState

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
from .coordinator import ZinvoltConfigEntry, ZinvoltDeviceCoordinator


@dataclass(kw_only=True, frozen=True)
class ZinvoltBatteryStateDescription(BinarySensorEntityDescription):
    """Binary sensor description for Zinvolt battery state."""

    is_on_fn: Callable[[BatteryState], bool]


SENSORS: tuple[ZinvoltBatteryStateDescription, ...] = (
    ZinvoltBatteryStateDescription(
        key="on_grid",
        translation_key="on_grid",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda state: state.current_power.on_grid,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZinvoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    async_add_entities(
        ZinvoltBatteryStateBinarySensor(coordinator, description)
        for description in SENSORS
        for coordinator in entry.runtime_data.values()
    )


class ZinvoltBatteryStateBinarySensor(
    CoordinatorEntity[ZinvoltDeviceCoordinator], BinarySensorEntity
):
    """Zinvolt battery state binary sensor."""

    _attr_has_entity_name = True
    entity_description: ZinvoltBatteryStateDescription

    def __init__(
        self,
        coordinator: ZinvoltDeviceCoordinator,
        description: ZinvoltBatteryStateDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}.{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer="Zinvolt",
            name=coordinator.data.name,
            serial_number=coordinator.data.serial_number,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
