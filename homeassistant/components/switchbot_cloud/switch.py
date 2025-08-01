"""Support for SwitchBot switch."""

import asyncio
from typing import Any

from switchbot_api import CommonCommands, Device, PowerState, Remote, SwitchBotAPI

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        await self.send_api_command(CommonCommands.ON)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.send_api_command(CommonCommands.OFF)
        self._attr_is_on = False
        self.async_write_ha_state()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return
        self._attr_is_on = self.coordinator.data.get("power") == PowerState.ON.value


class SwitchBotCloudRemoteSwitch(SwitchBotCloudSwitch):
    """Representation of a SwitchBot switch provider by a remote."""

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""


class SwitchBotCloudPlugSwitch(SwitchBotCloudSwitch):
    """Representation of a SwitchBot plug switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET


class SwitchBotCloudRelaySwitchSwitch(SwitchBotCloudSwitch):
    """Representation of a SwitchBot relay switch."""

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return
        self._attr_is_on = self.coordinator.data.get("switchStatus") == 1


class SwitchBotCloudRelaySwitch2PMSwitch(SwitchBotCloudSwitch):
    """Representation of a SwitchBot relay switch."""

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Init SwitchBotCloudRelaySwitch2PMSwitch."""
        super().__init__(api, device, coordinator)
        if self._attr_unique_id is not None:
            self.real_unique_id = self._attr_unique_id.split("-")[0]
            self.channel = self._attr_unique_id.split("-")[1]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._attr_unique_id is not None:
            await self._api.send_command(
                self.real_unique_id, command=CommonCommands.ON, parameters=self.channel
            )
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._attr_unique_id is not None:
            await self._api.send_command(
                self.real_unique_id, command=CommonCommands.OFF, parameters=self.channel
            )
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        self._attr_is_on = self.coordinator.data.get(f"switch{self.channel}Status") == 1


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudSwitch:
    """Make a SwitchBotCloudSwitch or SwitchBotCloudRemoteSwitch."""
    if isinstance(device, Remote):
        return SwitchBotCloudRemoteSwitch(api, device, coordinator)
    if "Plug" in device.device_type:
        return SwitchBotCloudPlugSwitch(api, device, coordinator)
    if device.device_type in [
        "Relay Switch 1PM",
        "Relay Switch 1",
    ]:
        return SwitchBotCloudRelaySwitchSwitch(api, device, coordinator)
    if "Bot" in device.device_type:
        return SwitchBotCloudSwitch(api, device, coordinator)
    if device.device_type in [
        "Relay Switch 2PM",
    ]:
        return SwitchBotCloudRelaySwitch2PMSwitch(api, device, coordinator)
    raise NotImplementedError(f"Unsupported device type: {device.device_type}")
