"""Support for TP-Link thermostats."""

from __future__ import annotations

import logging
from typing import Any

from kasa import Device, DeviceType
from kasa.smart.modules.temperaturecontrol import ThermostatState

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after
from .models import TPLinkData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up thermostats."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities: list[TPLinkClimate] = []
    # As there are no standalone thermostats, we just iterate over the children.
    entities.extend(
        TPLinkClimate(child, parent_coordinator)
        for child in device.children
        if child.device_type == DeviceType.Thermostat
    )

    async_add_entities(entities)


class TPLinkClimate(CoordinatedTPLinkEntity, ClimateEntity):
    """Representation of a TPLink thermostat."""

    # TODO: should this use ClimateEntityDescription?

    device: Device
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    # This disables the warning for async_turn_{on,off}.
    _enable_turn_on_off_backwards_compatibility = False
    # TODO: use unit from the device
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_precision = PRECISION_WHOLE

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the switch."""
        self._attr_unique_id = f"{device.device_id}_climate"
        super().__init__(device, coordinator)
        self._temp_feature = self.device.features["temperature"]
        self._target_feature = self.device.features["target_temperature"]
        self._state_feature = self.device.features["state"]
        self._mode_feature = self.device.features["mode"]
        self._async_update_attrs()

    @async_refresh_after
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._target_feature.set_value(int(temperature))

    @async_refresh_after
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode (on/off)."""
        if hvac_mode is HVACMode.HEAT:
            await self._state_feature.set_value(True)
        elif hvac_mode is HVACMode.OFF:
            await self._state_feature.set_value(False)
        else:
            _LOGGER.warning("Tried to set unsupported mode: %s", hvac_mode)

    @async_refresh_after
    async def async_turn_on(self) -> None:
        """Turn heating on."""
        await self._state_feature.set_value(True)

    @async_refresh_after
    async def async_turn_off(self) -> None:
        """Turn heating off."""
        await self._state_feature.set_value(False)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_min_temp = self._target_feature.minimum_value
        self._attr_max_temp = self._target_feature.maximum_value
        self._attr_target_temperature = self._target_feature.value

        self._attr_current_temperature = self._temp_feature.value
        # TODO: use unit from the device
        # self._attr_temperature_unit = self._temp_feature.unit

        self._attr_hvac_mode = (
            HVACMode.HEAT if self._state_feature.value else HVACMode.OFF
        )

        STATE_TO_ACTION = {
            ThermostatState.Idle: HVACAction.IDLE,
            ThermostatState.Heating: HVACAction.HEATING,
            ThermostatState.Off: HVACAction.OFF,
        }
        if (
            self._mode_feature.value not in STATE_TO_ACTION
            and self._attr_hvac_action is not HVACAction.OFF
        ):
            _LOGGER.warning(
                "Unknown thermostat state, defaulting to OFF: %s",
                self._mode_feature.value,
            )
            self._attr_hvac_action = HVACAction.OFF
            return

        self._attr_hvac_action = STATE_TO_ACTION[self._mode_feature.value]
