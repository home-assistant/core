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
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.shelly import BlockDeviceWrapper
from homeassistant.components.shelly.entity import ShellyBlockEntity
from homeassistant.components.shelly.utils import get_device_entry_gen
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
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
    blocks = [block for block in wrapper.device.blocks if hasattr(block, "targetTemp")]

    if not blocks:
        return

    async_add_entities(ShellyClimate(wrapper, block) for block in blocks)


class ShellyClimate(ShellyBlockEntity, RestoreEntity, ClimateEntity):
    """Representation of a KNX climate device."""

    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_AUTO]
    _attr_icon = "hass:thermostat"
    _attr_max_temp = SHTRV_01_TEMPERATURE_SETTINGS["max"]
    _attr_min_temp = SHTRV_01_TEMPERATURE_SETTINGS["min"]
    _attr_supported_features: int = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_target_temperature_step = SHTRV_01_TEMPERATURE_SETTINGS["step"]
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, wrapper: BlockDeviceWrapper, block: Block) -> None:
        """Initialize climate."""
        super().__init__(wrapper, block)

        self.wrapper = wrapper
        self.block = block
        self.control_result: dict[str, Any] | None = None

        self._attr_name = self.wrapper.name
        self._attr_unique_id = f"{self.wrapper.mac}-climate"
        self._attr_preset_modes: list[str] = wrapper.device.settings[
            "schedule_profile_names"
        ]
        self._attr_preset_modes.insert(0, "None")

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        return cast(float, self.block.targetTemp)

    @property
    def current_temperature(self) -> float | None:
        """Set current temperature."""
        return cast(float, self.block.temp)

    # @property
    # def is_available(self) -> bool:
    #     """Device a vailability."""
    #     return not cast(bool, self.block.valveError)

    @property
    def hvac_mode(self) -> str:
        """HVAC current mode."""
        if not hasattr(self.block, "mode") or self._check_is_off():
            return HVAC_MODE_OFF

        if cast(int, self.block.mode) != 0:
            return HVAC_MODE_AUTO
        return HVAC_MODE_HEAT

    @property
    def preset_mode(self) -> str | None:
        """Preset current mode."""
        if not hasattr(self.block, "mode"):
            return None
        return self._attr_preset_modes[cast(int, self.block.mode)]

    @property
    def hvac_action(self) -> str | None:
        """HVAC current action."""
        if self._check_is_off():
            return CURRENT_HVAC_OFF
        return CURRENT_HVAC_HEAT

    def _check_is_off(self) -> bool:
        """Return if valve is off or on."""
        return bool(
            not self.target_temperature
            or (self.target_temperature <= self._attr_min_temp)
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self) -> None:
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()

    async def set_state_full_path(self, path: str, **kwargs: Any) -> Any:
        """Set block state (HTTP request)."""
        _LOGGER.debug("Setting state for entity %s, state: %s", self.name, kwargs)
        try:
            async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
                return await self.block.set_state_full_path(path, **kwargs)
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
        await self.set_state_full_path(
            "settings?target_t_enabled=1", target_t=f"{current_temp}"
        )
        if self._check_is_off():
            self._hvac_action = CURRENT_HVAC_OFF
            self.async_set_hvac_mode(HVAC_MODE_OFF)
        else:
            self._hvac_action = CURRENT_HVAC_HEAT
            self.async_set_hvac_mode(
                HVAC_MODE_AUTO if self.preset_mode else HVAC_MODE_HEAT
            )
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            await self.set_state_full_path("settings", schedule_profile=1)
        else:
            await self.set_state_full_path("settings", schedule_profile=0)
        if hvac_mode == HVAC_MODE_OFF:
            await self.set_state_full_path(
                "settings?target_t_enabled=1", target_t=f"{self._attr_min_temp}"
            )
            self._hvac_action = CURRENT_HVAC_OFF
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if not self._attr_preset_modes:
            return
        if preset_mode == "None":
            await self.set_state_full_path("settings", schedule_profile=0)
            await self.async_set_hvac_mode(HVAC_MODE_HEAT)
        else:
            await self.set_state_full_path(
                "settings",
                schedule_profile=f"{self._attr_preset_modes.index(preset_mode)}",
            )
            await self.async_set_hvac_mode(HVAC_MODE_AUTO)
        self.async_write_ha_state()
