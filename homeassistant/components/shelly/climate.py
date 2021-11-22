"""Climate support for Shelly."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Final, cast

from aioshelly.block_device import Block
import async_timeout

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.shelly import BlockDeviceWrapper
from homeassistant.components.shelly.entity import ShellyBlockEntity
from homeassistant.components.shelly.utils import get_device_entry_gen
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    AIOSHELLY_DEVICE_TIMEOUT_SEC,
    BLOCK,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    SHTRV_01_TEMPERATURE_SETTINGS,
)

_LOGGER: Final = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate device."""

    if get_device_entry_gen(config_entry) == 2:
        return

    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][BLOCK]
    for block in wrapper.device.blocks:
        if block.type == "device":
            device_block = block
        if hasattr(block, "targetTemp"):
            sensor_block = block

    if sensor_block and device_block:
        async_add_entities([ShellyClimate(wrapper, sensor_block, device_block)])


class ShellyClimate(ShellyBlockEntity, RestoreEntity, ClimateEntity):
    """Representation of a Shelly climate device."""

    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT]
    _attr_icon = "mdi:thermostat"
    _attr_max_temp = SHTRV_01_TEMPERATURE_SETTINGS["max"]
    _attr_min_temp = SHTRV_01_TEMPERATURE_SETTINGS["min"]
    _attr_supported_features: int = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_target_temperature_step = SHTRV_01_TEMPERATURE_SETTINGS["step"]
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self, wrapper: BlockDeviceWrapper, sensor_block: Block, device_block: Block
    ) -> None:
        """Initialize climate."""
        super().__init__(wrapper, sensor_block)

        self.device_block = device_block

        assert self.block.channel

        self.control_result: dict[str, Any] | None = None

        self._attr_name = self.wrapper.name
        self._attr_unique_id = self.wrapper.mac
        self._attr_preset_modes: list[str] = [
            PRESET_NONE,
            *wrapper.device.settings["thermostats"][int(self.block.channel)][
                "schedule_profile_names"
            ],
        ]

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        return cast(float, self.block.targetTemp)

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return cast(float, self.block.temp)

    @property
    def available(self) -> bool:
        """Device availability."""
        return not cast(bool, self.device_block.valveError)

    @property
    def hvac_mode(self) -> str:
        """HVAC current mode."""
        if self.device_block.mode is None or self._check_is_off():
            return HVAC_MODE_OFF

        return HVAC_MODE_HEAT

    @property
    def preset_mode(self) -> str | None:
        """Preset current mode."""
        if self.device_block.mode is None:
            return None
        return self._attr_preset_modes[cast(int, self.device_block.mode)]

    @property
    def hvac_action(self) -> str | None:
        """HVAC current action."""
        if self.device_block.status is None or self._check_is_off():
            return CURRENT_HVAC_OFF

        return (
            CURRENT_HVAC_IDLE if self.device_block.status == "0" else CURRENT_HVAC_HEAT
        )

    def _check_is_off(self) -> bool:
        """Return if valve is off or on."""
        return bool(
            self.target_temperature is None
            or (self.target_temperature <= self._attr_min_temp)
        )

    async def set_state_full_path(self, **kwargs: Any) -> Any:
        """Set block state (HTTP request)."""
        _LOGGER.debug("Setting state for entity %s, state: %s", self.name, kwargs)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                return await self.wrapper.device.http_request(
                    "get", f"thermostat/{self.block.channel}", kwargs
                )
        except (asyncio.TimeoutError, OSError) as err:
            _LOGGER.error(
                "Setting state for entity %s failed, state: %s, error: %s",
                self.name,
                kwargs,
                repr(err),
            )
            self.wrapper.last_update_success = False
            return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (current_temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.set_state_full_path(target_t_enabled=1, target_t=f"{current_temp}")

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.set_state_full_path(
                target_t_enabled=1, target_t=f"{self._attr_min_temp}"
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if not self._attr_preset_modes:
            return

        preset_index = self._attr_preset_modes.index(preset_mode)
        await self.set_state_full_path(
            schedule=(0 if preset_index == 0 else 1),
            schedule_profile=f"{preset_index}",
        )
