"""Base class for the La Marzocco entities."""

from collections.abc import Callable
from dataclasses import dataclass

from pylamarzocco.const import FirmwareType

from homeassistant.const import CONF_ADDRESS, CONF_MAC
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoEntityDescription(EntityDescription):
    """Description for all LM entities."""

    available_fn: Callable[[LaMarzoccoUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[LaMarzoccoUpdateCoordinator], bool] = lambda _: True


class LaMarzoccoBaseEntity(
    CoordinatorEntity[LaMarzoccoUpdateCoordinator],
):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=device.dashboard.name,
            manufacturer="La Marzocco",
            model=device.dashboard.model_name.value,
            model_id=device.dashboard.model_code.value,
            serial_number=device.serial_number,
            sw_version=device.settings.firmwares[FirmwareType.MACHINE].build_version,
        )
        connections: set[tuple[str, str]] = set()
        if coordinator.config_entry.data.get(CONF_ADDRESS):
            connections.add(
                (CONNECTION_NETWORK_MAC, coordinator.config_entry.data[CONF_ADDRESS])
            )
        if coordinator.config_entry.data.get(CONF_MAC):
            connections.add(
                (CONNECTION_BLUETOOTH, coordinator.config_entry.data[CONF_MAC])
            )
        if connections:
            self._attr_device_info.update(DeviceInfo(connections=connections))


class LaMarzoccoEntity(LaMarzoccoBaseEntity):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if super().available:
            return self.entity_description.available_fn(self.coordinator)
        return False

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        entity_description: LaMarzoccoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
