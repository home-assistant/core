"""Support for valves through the SmartThings cloud API."""

from __future__ import annotations

from pysmartthings import SmartThings
from pysmartthings.models import Attribute, Capability, Category, Command

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .entity import SmartThingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add valves for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsValve(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.VALVE in device.status["main"]
    )


class SmartThingsValve(SmartThingsEntity, ValveEntity):
    """Define a SmartThings valve."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Init the class."""
        super().__init__(client, device, [Capability.VALVE])
        self._attr_device_class = {
            Category.WATER_VALVE: ValveDeviceClass.WATER,
            Category.GAS_VALVE: ValveDeviceClass.GAS,
        }.get(
            device.device.components[0].user_category
            or device.device.components[0].manufacturer_category
        )

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.execute_device_command(
            Capability.VALVE,
            Command.OPEN,
        )

    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self.execute_device_command(
            Capability.VALVE,
            Command.CLOSE,
        )

    @property
    def is_closed(self) -> bool:
        """Return if the valve is closed."""
        return self.get_attribute_value(Capability.VALVE, Attribute.VALVE) == "closed"
