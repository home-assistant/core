"""Support for SwitchBot switch."""

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
        self._current_switch_index = self.__get_current_switch_index()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._attr_unique_id is None:
            return
        if f"-{self._current_switch_index}" in self._attr_unique_id:
            self._attr_unique_id = self._attr_unique_id.replace(
                f"-{self._current_switch_index}", ""
            )

        await self.send_api_command(
            command=CommonCommands.ON, parameters=str(self._current_switch_index)
        )

        if f"-{self._current_switch_index}" not in self._attr_unique_id:
            self._attr_unique_id = (
                self._attr_unique_id + f"-{self._current_switch_index}"
            )

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._attr_unique_id is None:
            return
        if f"-{self._current_switch_index}" in self._attr_unique_id:
            self._attr_unique_id = self._attr_unique_id.replace(
                f"-{self._current_switch_index}", ""
            )

        await self.send_api_command(
            command=CommonCommands.OFF, parameters=str(self._current_switch_index)
        )

        if f"-{self._current_switch_index}" not in self._attr_unique_id:
            self._attr_unique_id = (
                self._attr_unique_id + f"-{self._current_switch_index}"
            )
        self._attr_is_on = False
        self.async_write_ha_state()

    def __get_current_switch_index(self) -> int | None:
        """Get current Switch index."""
        if not self.coordinator.data:
            return None
        name: str | None = (
            self._attr_device_info.get("name") if self._attr_device_info else None
        )
        if name is None:
            return None
        return int(name.split("-")[-1].strip())

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return
        self._attr_is_on = (
            self.coordinator.data.get(f"switch{self._current_switch_index}Status") == 1
        )


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
    if device.device_type in [
        "Relay Switch 2PM",
    ]:
        return SwitchBotCloudRelaySwitch2PMSwitch(api, device, coordinator)
    if "Bot" in device.device_type:
        return SwitchBotCloudSwitch(api, device, coordinator)
    raise NotImplementedError(f"Unsupported device type: {device.device_type}")
