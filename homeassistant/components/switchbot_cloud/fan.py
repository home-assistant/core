"""Support for the Switchbot Battery Circulator fan."""

from typing import Any

from switchbot_api import (
    BatteryCirculatorFanCommands,
    BatteryCirculatorFanMode,
    CommonCommands,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
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
    _attr_preset_modes = list(BatteryCirculatorFanMode)

    _attr_is_on: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        if (
            self._attr_is_on is None
            and self.percentage == 0
            and self.preset_mode is None
        ):
            response: dict | None = self.coordinator.data
            assert response is not None
            power: str | None = response.get("power")
            mode: str | None = response.get("mode")
            fan_speed: str | None = response.get("fanSpeed")
            assert fan_speed is not None
            self.preset_mode = mode if mode else BatteryCirculatorFanMode.DIRECT.value
            self.percentage = (
                int(fan_speed)
                if self.preset_mode in BatteryCirculatorFanMode.DIRECT.value
                else 0
            )
            assert power is not None
            self._attr_is_on = "on" in power
        return self._attr_is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        response: dict | None = await self._api.get_status(self.unique_id)
        assert response is not None
        power: str | None = response.get("power")
        if self._attr_is_on is False and (power and "off" in power):
            await self.send_api_command(CommonCommands.ON)
            self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""

        response: dict | None = await self._api.get_status(self.unique_id)
        assert response is not None
        power: str | None = response.get("power")
        if self._attr_is_on is True and (power and "on" in power):
            await self.send_api_command(CommonCommands.OFF)
            self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        assert 0 <= percentage <= 100
        response: dict | None = await self._api.get_status(self.unique_id)
        assert response is not None
        mode: str | None = response.get("mode")
        if mode is not None:
            if mode in BatteryCirculatorFanMode.DIRECT.value:
                await self.send_api_command(
                    command=BatteryCirculatorFanCommands.SET_WIND_SPEED,
                    parameters=str(percentage),
                )
                self.percentage = percentage
                self.preset_mode = BatteryCirculatorFanMode.DIRECT.value
            else:
                self.percentage = 0
                self.preset_mode = mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        assert preset_mode in [item.value for item in list(BatteryCirculatorFanMode)]
        await self.send_api_command(
            command=BatteryCirculatorFanCommands.SET_WIND_MODE,
            parameters=preset_mode,
        )
        self.preset_mode = preset_mode
        response: dict | None = await self._api.get_status(self.unique_id)
        assert response is not None
        fan_speed: int | None = response.get("fanSpeed")
        if preset_mode in BatteryCirculatorFanMode.DIRECT.value:
            self.percentage = int(fan_speed) if fan_speed else 0
        else:
            self.percentage = 0

        self.async_write_ha_state()
