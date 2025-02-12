"""Support for valves through the SmartThings cloud API."""

from __future__ import annotations

from pysmartthings.models import Attribute, Capability, Category, Command

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartThingsConfigEntry, SmartThingsDeviceCoordinator
from .entity import SmartThingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add valves for a config entry."""
    devices = entry.runtime_data.devices
    async_add_entities(
        SmartThingsValve(device)
        for device in devices
        if Capability.VALVE in device.data
    )


class SmartThingsValve(SmartThingsEntity, ValveEntity):
    """Define a SmartThings valve."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False

    def __init__(self, device: SmartThingsDeviceCoordinator) -> None:
        """Init the class."""
        super().__init__(device)
        self._attr_device_class = {
            Category.WATER_VALVE: ValveDeviceClass.WATER,
            Category.GAS_VALVE: ValveDeviceClass.GAS,
        }.get(
            device.device.components[0].user_category
            or device.device.components[0].manufacturer_category
        )

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.VALVE,
            Command.OPEN,
        )

    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.VALVE,
            Command.CLOSE,
        )

    @property
    def is_closed(self) -> bool:
        """Return if the valve is closed."""
        return self.get_attribute_value(Capability.VALVE, Attribute.VALVE) == "closed"
