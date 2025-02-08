"""Support for switches through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings.models import Attribute, Capability, Command

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartThingsConfigEntry
from .entity import SmartThingsEntity

CAPABILITIES = (
    Capability.SWITCH_LEVEL,
    Capability.COLOR_CONTROL,
    Capability.COLOR_TEMPERATURE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    devices = entry.runtime_data.devices
    async_add_entities(
        SmartThingsSwitch(device)
        for device in devices
        if Capability.SWITCH in device.data
        and not any(capability in device.data for capability in CAPABILITIES)
    )


# def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
#     """Return all capabilities supported if minimum required are present."""
#     # Must be able to be turned on/off.
#     if Capability.switch in capabilities:
#         return [Capability.switch, Capability.energy_meter, Capability.power_meter]
#     return None


class SmartThingsSwitch(SmartThingsEntity, SwitchEntity):
    """Define a SmartThings switch."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.SWITCH,
            Command.OFF,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.SWITCH,
            Command.ON,
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.coordinator.data[Capability.SWITCH].get(Attribute.SWITCH) == "on"
