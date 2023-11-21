"""Support for Modbus Register sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FlaktgroupModbusDataUpdateCoordinator
from .const import (
    CONF_DEVICE_INFO,
    CONF_MODBUS_COORDINATOR,
    DOMAIN,
    FanModes,
    HoldingRegisters,
    Presets,
)
from .modbus_coordinator import ModbusDatapointContext, ModbusDatapointDescriptionMixin

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fläktgroup from a config entry."""
    hass_config = hass.data[DOMAIN][config_entry.entry_id]
    device_info = hass_config[CONF_DEVICE_INFO]
    entities = [
        FlaktgroupClimate(
            hass_config[CONF_MODBUS_COORDINATOR],
            device_info,
        ),
    ]
    async_add_entities(entities)


@dataclass
class ModbusDatapointClimateDescription(
    ModbusDatapointDescriptionMixin, ClimateEntityDescription
):
    """Modbus Datapoint Climate Description."""


class FlaktgroupClimate(CoordinatorEntity, RestoreEntity, ClimateEntity):
    """Flaktgroup Climate."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        coordinator: FlaktgroupModbusDataUpdateCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Flaktgroup Climate."""
        self._attr_unique_id = f"{device_info.get('name')}_climate"
        self._attr_device_info = device_info
        self.entity_description = ClimateEntityDescription(
            key="climate_entity", translation_key="climate_entity", has_entity_name=True
        )

        self._attr_min_temp = 7
        self._attr_max_temp = 35
        self._attr_target_temperature_step = 0.5

        self._attr_fan_modes: list[str] = [str(fan_mode.value) for fan_mode in FanModes]
        self._attr_hvac_modes = []
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_preset_modes: list[str] = [str(preset.value) for preset in Presets]
        self._attr_preset_mode = None
        super().__init__(
            coordinator,
            ModbusDatapointContext(
                {
                    HoldingRegisters.FAN_MODE.value,
                    HoldingRegisters.PRESET_MODE.value,
                    HoldingRegisters.HUMIDITY_1.value,
                    HoldingRegisters.SUPPLY_AIR_TEMPERATURE.value,
                    HoldingRegisters.TEMPERATURE_SET_POINT.value,
                },
                lambda: self.enabled,
            ),
        )

    async def async_added_to_hass(self) -> None:
        """Restore state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state != STATE_UNAVAILABLE:
            if fan_mode := state.attributes.get("fan_mode"):
                self._attr_fan_mode = fan_mode
            if min_temp := state.attributes.get("min_temp"):
                self._attr_min_temp = min_temp
            if max_temp := state.attributes.get("max_temp"):
                self._attr_max_temp = max_temp
            if target_temperature := state.attributes.get("temperature"):
                self._attr_target_temperature = target_temperature
            if current_temperature := state.attributes.get("current_temperature"):
                self._attr_current_temperature = current_temperature
            if current_humidity := state.attributes.get("current_humidity"):
                self._attr_current_humidity = current_humidity

    def _handle_coordinator_update(self) -> None:
        if (
            value := self.coordinator.data.get(
                HoldingRegisters.TEMPERATURE_SET_POINT.value
            )
        ) is not None:
            self._attr_target_temperature = value * 0.1

        if (
            value := self.coordinator.data.get(
                HoldingRegisters.SUPPLY_AIR_TEMPERATURE.value
            )
        ) is not None:
            self._attr_current_temperature = value * 0.1

        if (
            value := self.coordinator.data.get(HoldingRegisters.HUMIDITY_1.value)
        ) is not None:
            self._attr_current_humidity = value

        if (
            value := self.coordinator.data.get(HoldingRegisters.FAN_MODE.value)
        ) is not None:
            self._attr_fan_mode = str(value)

        if (
            value := self.coordinator.data.get(HoldingRegisters.PRESET_MODE.value)
        ) is not None:
            self._attr_preset_mode = str(value)

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode in self._attr_preset_modes:
            await self.coordinator.write(
                HoldingRegisters.PRESET_MODE.value, int(preset_mode)
            )
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode in self._attr_fan_modes:
            await self.coordinator.write(HoldingRegisters.FAN_MODE.value, int(fan_mode))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Fläktgroup modes are controlled with presets since HVACMode Enum does not contain required modes."""

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.coordinator.write(
            HoldingRegisters.TEMPERATURE_SET_POINT.value,
            round(float(kwargs[ATTR_TEMPERATURE]) / 0.1),
        )
        await self.coordinator.async_request_refresh()

    @property
    def fan_mode(self) -> str | None:
        """Get current fan mode."""
        if self.preset_mode == str(Presets.MANUAL):
            return super().fan_mode
        return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Get available fan modes."""
        if self.preset_mode == str(Presets.MANUAL):
            return super().fan_modes
        return []
