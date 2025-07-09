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
        return self._attr_is_on

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return

        power: str | None = self.coordinator.data.get("power")
        mode: str | None = self.coordinator.data.get("mode")
        fan_speed: str | None = self.coordinator.data.get("fanSpeed")
        assert power is not None
        self._attr_is_on = "on" in power
        assert mode is not None
        self.preset_mode = mode
        assert fan_speed is not None
        self.percentage = int(fan_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.coordinator.async_refresh()
        await self.send_api_command(CommonCommands.ON)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.async_refresh()
        await self.send_api_command(CommonCommands.OFF)
        self.percentage = 0
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self.coordinator.async_refresh()
        if self.is_on and self.preset_mode == BatteryCirculatorFanMode.DIRECT.value:
            await self.send_api_command(
                command=BatteryCirculatorFanCommands.SET_WIND_SPEED,
                parameters=str(percentage),
            )
            self.percentage = percentage
        else:
            self.percentage = 0

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.coordinator.async_refresh()
        await self.send_api_command(
            command=BatteryCirculatorFanCommands.SET_WIND_MODE,
            parameters=preset_mode,
        )
        self.preset_mode = preset_mode

        if self.preset_mode != BatteryCirculatorFanMode.DIRECT.value:
            self.percentage = 0
        self.async_write_ha_state()
