"""Support for the Switchbot Bot as a Button."""

from typing import Any

from switchbot_api import CommonCommands

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN, SwitchBotCloudFanCommandS, SwitchBotCloudFanMode
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudFan(data.api, device, coordinator)
        for device, coordinator in data.devices.fans
    )


class SwitchBotCloudFan(SwitchBotCloudEntity, FanEntity):
    """Representation of a SwitchBot Battery Circulator Fan."""

    _attr_name = None

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = [item.value for item in SwitchBotCloudFanMode.get_all_obj()]
    _attr_is_on = False

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        if self.percentage == 0 and self.preset_mode is None:
            response = self.coordinator.data
            if response:
                mode = response.get("mode")
                fan_speed = response.get("fanSpeed")
                power = response.get("power")
                self.preset_mode = mode if mode else SwitchBotCloudFanMode.DIRECT.value
                self.percentage = fan_speed if fan_speed else -1
                return power is not None and "on" in power
        return super().is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        response = await self._api.get_status(self._attr_unique_id)
        self.percentage = response.get("fanSpeed")
        self.preset_mode = response.get("mode")
        self._attr_preset_mode = self.preset_mode
        await self.send_api_command(CommonCommands.ON)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.send_api_command(CommonCommands.OFF)
        self.percentage = -1
        self.preset_mode = None
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        assert 0 <= percentage <= 100
        response = await self._api.get_status(self._attr_unique_id)
        if SwitchBotCloudFanMode.DIRECT.value in response.get("mode"):
            await self.send_api_command(
                command=SwitchBotCloudFanCommandS.SET_WIND_SPEED,
                parameters=str(percentage),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        assert preset_mode in [
            item.value for item in SwitchBotCloudFanMode.get_all_obj()
        ]
        await self.send_api_command(
            command=SwitchBotCloudFanCommandS.SET_WIND_MODE, parameters=preset_mode
        )
        self.preset_mode = preset_mode
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
