"""Climate support for Shelly."""
from __future__ import annotations

import asyncio
import logging
from types import MappingProxyType
from typing import Any, Final, cast

from aioshelly.block_device import Block
import async_timeout

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, ClimateEntity
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
from homeassistant.components.shelly.utils import get_device_entry_gen
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import device_registry, entity, entity_registry
from homeassistant.helpers.entity import DeviceInfo
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

    wrapper: BlockDeviceWrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ][BLOCK]

    if wrapper.device.initialized:
        await async_setup_climate_entities(async_add_entities, wrapper)
    else:
        await async_restore_climate_entities(
            hass, config_entry, async_add_entities, wrapper
        )


async def async_setup_climate_entities(
    async_add_entities: AddEntitiesCallback,
    wrapper: BlockDeviceWrapper,
) -> None:
    """Set up online climate devices."""

    device_block: Block | None = None
    sensor_block: Block | None = None

    assert wrapper.device.blocks

    for block in wrapper.device.blocks:
        if block.type == "device":
            device_block = block
        if hasattr(block, "targetTemp"):
            sensor_block = block

    if sensor_block and device_block:
        _LOGGER.debug("Setup online climate device %s", wrapper.name)
        async_add_entities([BlockSleepingClimate(wrapper, sensor_block, device_block)])


async def async_restore_climate_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    wrapper: BlockDeviceWrapper,
) -> None:
    """Restore sleeping climate devices."""

    ent_reg = await entity_registry.async_get_registry(hass)
    entries = entity_registry.async_entries_for_config_entry(
        ent_reg, config_entry.entry_id
    )

    for entry in entries:

        if entry.domain != CLIMATE_DOMAIN:
            continue

        _LOGGER.debug("Setup sleeping climate device %s", wrapper.name)
        _LOGGER.debug("Found entry %s [%s]", entry.original_name, entry.domain)
        async_add_entities([BlockSleepingClimate(wrapper, None, None, entry)])


class BlockSleepingClimate(
    RestoreEntity,
    ClimateEntity,
    entity.Entity,
):
    """Representation of a Shelly climate device."""

    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT]
    _attr_icon = "mdi:thermostat"
    _attr_max_temp = SHTRV_01_TEMPERATURE_SETTINGS["max"]
    _attr_min_temp = SHTRV_01_TEMPERATURE_SETTINGS["min"]
    _attr_supported_features: int = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_target_temperature_step = SHTRV_01_TEMPERATURE_SETTINGS["step"]
    _attr_temperature_unit = TEMP_CELSIUS

    # pylint: disable=super-init-not-called
    def __init__(
        self,
        wrapper: BlockDeviceWrapper,
        sensor_block: Block | None,
        device_block: Block | None,
        entry: entity_registry.RegistryEntry | None = None,
    ) -> None:
        """Initialize climate."""

        self.wrapper = wrapper
        self.block: Block | None = sensor_block
        self.control_result: dict[str, Any] | None = None
        self.device_block: Block | None = device_block
        self.last_state: State | None = None
        self.last_state_attributes: MappingProxyType[str, Any]
        self._preset_modes: list[str] = []

        if self.block is not None and self.device_block is not None:
            self._unique_id = f"{self.wrapper.mac}-{self.block.description}"
            assert self.block.channel
            self._preset_modes = [
                PRESET_NONE,
                *wrapper.device.settings["thermostats"][int(self.block.channel)][
                    "schedule_profile_names"
                ],
            ]
        elif entry is not None:
            self._unique_id = entry.unique_id

    @property
    def unique_id(self) -> str:
        """Set unique id of entity."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Name of entity."""
        return self.wrapper.name

    @property
    def should_poll(self) -> bool:
        """If device should be polled."""
        return False

    @property
    def target_temperature(self) -> float | None:
        """Set target temperature."""
        if self.block is not None:
            return cast(float, self.block.targetTemp)
        return self.last_state_attributes.get("temperature")

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        if self.block is not None:
            return cast(float, self.block.temp)
        return self.last_state_attributes.get("current_temperature")

    @property
    def available(self) -> bool:
        """Device availability."""
        if self.device_block is not None:
            return not cast(bool, self.device_block.valveError)
        return self.wrapper.last_update_success

    @property
    def hvac_mode(self) -> str:
        """HVAC current mode."""
        if self.device_block is None:
            return self.last_state.state if self.last_state else HVAC_MODE_OFF
        if self.device_block.mode is None or self._check_is_off():
            return HVAC_MODE_OFF

        return HVAC_MODE_HEAT

    @property
    def preset_mode(self) -> str | None:
        """Preset current mode."""
        if self.device_block is None:
            return self.last_state_attributes.get("preset_mode")
        if self.device_block.mode is None:
            return PRESET_NONE
        return self._preset_modes[cast(int, self.device_block.mode)]

    @property
    def hvac_action(self) -> str | None:
        """HVAC current action."""
        if (
            self.device_block is None
            or self.device_block.status is None
            or self._check_is_off()
        ):
            return CURRENT_HVAC_OFF

        return (
            CURRENT_HVAC_HEAT if bool(self.device_block.status) else CURRENT_HVAC_IDLE
        )

    @property
    def preset_modes(self) -> list[str]:
        """Preset available modes."""
        return self._preset_modes

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def channel(self) -> str | None:
        """Device channel."""
        if self.block is not None:
            return self.block.channel
        return self.last_state_attributes.get("channel")

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
                    "get", f"thermostat/{self.channel}", kwargs
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
        if not self._preset_modes:
            return

        preset_index = self._preset_modes.index(preset_mode)

        if preset_index == 0:
            await self.set_state_full_path(schedule=0)
        else:
            await self.set_state_full_path(
                schedule=1, schedule_profile=f"{preset_index}"
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        _LOGGER.info("Restoring entity %s", self.name)

        last_state = await self.async_get_last_state()

        if last_state is not None:
            self.last_state = last_state
            self.last_state_attributes = self.last_state.attributes
            self._preset_modes = cast(
                list, self.last_state.attributes.get("preset_modes")
            )

        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self) -> None:
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        if not self.wrapper.device.initialized:
            self.async_write_ha_state()
            return

        assert self.wrapper.device.blocks

        for block in self.wrapper.device.blocks:
            if block.type == "device":
                self.device_block = block
            if hasattr(block, "targetTemp"):
                self.block = block

                _LOGGER.debug("Entity %s attached to block", self.name)
                self.async_write_ha_state()
                return
