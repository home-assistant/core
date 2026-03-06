"""Base entity for OpenDisplay devices."""

from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription

from . import OpenDisplayConfigEntry
from .coordinator import OpenDisplayCoordinator


class OpenDisplayEntity(PassiveBluetoothCoordinatorEntity[OpenDisplayCoordinator]):
    """Base class for all OpenDisplay entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenDisplayCoordinator,
        entry: OpenDisplayConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"

        runtime = entry.runtime_data
        fw = runtime.firmware
        device_config = runtime.device_config
        is_flex = runtime.is_flex
        manufacturer = device_config.manufacturer
        display = device_config.displays[0]

        color_scheme_enum = display.color_scheme_enum
        color_scheme = (
            str(color_scheme_enum)
            if isinstance(color_scheme_enum, int)
            else color_scheme_enum.name
        )
        size = (
            f'{display.screen_diagonal_inches:.1f}"'
            if display.screen_diagonal_inches is not None
            else f"{display.pixel_width}x{display.pixel_height}"
        )

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=entry.title,
            manufacturer=manufacturer.manufacturer_name,
            model=f"{size} {color_scheme}",
            sw_version=f"{fw['major']}.{fw['minor']}",
            hw_version=(
                f"{manufacturer.board_type_name or manufacturer.board_type}"
                f" rev. {manufacturer.board_revision}"
            )
            if is_flex
            else None,
            configuration_url="https://opendisplay.org/firmware/config/"
            if is_flex
            else None,
        )
