"""Base class for the La Marzocco entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pylamarzocco.const import FirmwareType, MachineState, WidgetType
from pylamarzocco.models import MachineStatus

from homeassistant.const import CONF_ADDRESS, CONF_MAC
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    LaMarzoccoBluetoothUpdateCoordinator,
    LaMarzoccoUpdateCoordinator,
)


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoEntityDescription(EntityDescription):
    """Description for all LM entities."""

    available_fn: Callable[[LaMarzoccoUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[LaMarzoccoUpdateCoordinator], bool] = lambda _: True
    bt_offline_mode: bool = False


class LaMarzoccoBaseEntity(
    CoordinatorEntity[LaMarzoccoUpdateCoordinator],
):
    """Common elements for all entities."""

    _attr_has_entity_name = True
    _unavailable_when_machine_off = True

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.serial_number}_{key}"
        sw_version = (
            device.settings.firmwares[FirmwareType.MACHINE].build_version
            if FirmwareType.MACHINE in device.settings.firmwares
            else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=device.dashboard.name or self.coordinator.config_entry.title,
            manufacturer="La Marzocco",
            model=device.dashboard.model_name.value,
            model_id=device.dashboard.model_code.value,
            serial_number=device.serial_number,
            sw_version=sw_version,
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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        machine_state = (
            cast(
                MachineStatus,
                self.coordinator.device.dashboard.config[WidgetType.CM_MACHINE_STATUS],
            ).status
            if WidgetType.CM_MACHINE_STATUS in self.coordinator.device.dashboard.config
            else MachineState.OFF
        )
        return (
            super().available
            and not (
                self._unavailable_when_machine_off and machine_state is MachineState.OFF
            )
            and self.coordinator.update_success
        )


class LaMarzoccoEntity(LaMarzoccoBaseEntity):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if (
            self.entity_description.bt_offline_mode
            and self.bluetooth_coordinator is not None
        ):
            return self.bluetooth_coordinator.last_update_success
        if super().available:
            return self.entity_description.available_fn(self.coordinator)
        return False

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        entity_description: LaMarzoccoEntityDescription,
        bluetooth_coordinator: LaMarzoccoBluetoothUpdateCoordinator | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
        self.bluetooth_coordinator = bluetooth_coordinator

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added to hass."""
        await super().async_added_to_hass()
        if self.bluetooth_coordinator is not None:
            self.async_on_remove(
                self.bluetooth_coordinator.async_add_listener(self.async_write_ha_state)
            )
