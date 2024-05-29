"""Support for SwitchBot switch."""

from typing import Any

from switchbot_api import CommonCommands, Device, PowerState, Remote, SwitchBotAPI

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.switches
    )


class SwitchBotCloudSwitch(SwitchBotCloudEntity, SwitchEntity):
    """Representation of a SwitchBot switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_name = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.send_command(CommonCommands.ON)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.send_command(CommonCommands.OFF)
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return
        self._attr_is_on = self.coordinator.data.get("power") == PowerState.ON.value
        self.async_write_ha_state()


class SwitchBotCloudRemoteSwitch(SwitchBotCloudSwitch):
    """Representation of a SwitchBot switch provider by a remote."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""


class SwitchBotCloudPlugSwitch(SwitchBotCloudSwitch):
    """Representation of a SwitchBot plug switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudSwitch:
    """Make a SwitchBotCloudSwitch or SwitchBotCloudRemoteSwitch."""
    if isinstance(device, Remote):
        return SwitchBotCloudRemoteSwitch(api, device, coordinator)
    if "Plug" in device.device_type:
        return SwitchBotCloudPlugSwitch(api, device, coordinator)
    raise NotImplementedError(f"Unsupported device type: {device.device_type}")
