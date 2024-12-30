"""Support for TP-Link thermostats."""

from __future__ import annotations

import logging
from typing import Any, cast

from kasa import Device, DeviceType
from kasa.smart.modules.temperaturecontrol import ThermostatState

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import PRECISION_TENTHS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .const import UNIT_MAPPING
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after

# Upstream state to HVACAction
STATE_TO_ACTION = {
    ThermostatState.Idle: HVACAction.IDLE,
    ThermostatState.Heating: HVACAction.HEATING,
    ThermostatState.Off: HVACAction.OFF,
}


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    # As there are no standalone thermostats, we just iterate over the children.
    async_add_entities(
        TPLinkClimateEntity(child, parent_coordinator, parent=device)
        for child in device.children
        if child.device_type is DeviceType.Thermostat
    )


class TPLinkClimateEntity(CoordinatedTPLinkEntity, ClimateEntity):
    """Representation of a TPLink thermostat."""

    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_precision = PRECISION_TENTHS

    # This disables the warning for async_turn_{on,off}, can be removed later.

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        parent: Device,
    ) -> None:
        """Initialize the climate entity."""
        self._state_feature = device.features["state"]
        self._mode_feature = device.features["thermostat_mode"]
        self._temp_feature = device.features["temperature"]
        self._target_feature = device.features["target_temperature"]

        self._attr_min_temp = self._target_feature.minimum_value
        self._attr_max_temp = self._target_feature.maximum_value
        self._attr_temperature_unit = UNIT_MAPPING[cast(str, self._temp_feature.unit)]

        super().__init__(device, coordinator, parent=parent)

    @async_refresh_after
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        await self._target_feature.set_value(int(kwargs[ATTR_TEMPERATURE]))

    @async_refresh_after
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode (heat/off)."""
        if hvac_mode is HVACMode.HEAT:
            await self._state_feature.set_value(True)
        elif hvac_mode is HVACMode.OFF:
            await self._state_feature.set_value(False)
        else:
            raise ServiceValidationError(f"Tried to set unsupported mode: {hvac_mode}")

    @async_refresh_after
    async def async_turn_on(self) -> None:
        """Turn heating on."""
        await self._state_feature.set_value(True)

    @async_refresh_after
    async def async_turn_off(self) -> None:
        """Turn heating off."""
        await self._state_feature.set_value(False)

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_current_temperature = cast(float | None, self._temp_feature.value)
        self._attr_target_temperature = cast(float | None, self._target_feature.value)

        self._attr_hvac_mode = (
            HVACMode.HEAT if self._state_feature.value else HVACMode.OFF
        )

        if (
            self._mode_feature.value not in STATE_TO_ACTION
            and self._attr_hvac_action is not HVACAction.OFF
        ):
            _LOGGER.warning(
                "Unknown thermostat state, defaulting to OFF: %s",
                self._mode_feature.value,
            )
            self._attr_hvac_action = HVACAction.OFF
            return True

        self._attr_hvac_action = STATE_TO_ACTION[
            cast(ThermostatState, self._mode_feature.value)
        ]
        return True

    def _get_unique_id(self) -> str:
        """Return unique id."""
        return f"{self._device.device_id}_climate"
