"""Climate platform for Watts Vision integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from visionpluspython.models import ThermostatDevice

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WattsVisionConfigEntry
from .const import (
    HVAC_MODE_TO_THERMOSTAT,
    THERMOSTAT_MODE_TO_HVAC,
    UPDATE_DELAY_AFTER_COMMAND,
)
from .coordinator import WattsVisionCoordinator
from .entity import WattsVisionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattsVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Watts Vision climate entities from a config entry."""

    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            WattsVisionClimate(coordinator, device)
            for device in coordinator.data.values()
        ],
        update_before_add=True,
    )


class WattsVisionClimate(WattsVisionEntity, ClimateEntity):
    """Representation of a Watts Vision heater as a climate entity."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_name = None

    def __init__(
        self,
        coordinator: WattsVisionCoordinator,
        device: ThermostatDevice,
    ) -> None:
        """Initialize the climate entity."""

        super().__init__(coordinator, device.device_id)
        self._device = device

        self._attr_min_temp = device.min_allowed_temperature
        self._attr_max_temp = device.max_allowed_temperature

        if device.temperature_unit.upper() == "C":
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        else:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    @property
    def thermostat_device(self) -> ThermostatDevice | None:
        """Return the device as a ThermostatDevice if it's the correct type."""
        if self.device and isinstance(self.device, ThermostatDevice):
            return self.device
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.thermostat_device:
            return self.thermostat_device.current_temperature
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature setpoint."""
        if self.thermostat_device:
            return self.thermostat_device.setpoint
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        if self.thermostat_device:
            return THERMOSTAT_MODE_TO_HVAC.get(self.thermostat_device.thermostat_mode)
        return None

    async def async_request_refresh(self) -> None:
        """Request refresh for this specific entity only."""
        await self.coordinator.async_refresh_device(self.device_id)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self.coordinator.client.set_thermostat_temperature(
                self.device_id, temperature
            )
            _LOGGER.debug(
                "Successfully set temperature to %s for %s",
                temperature,
                self._attr_name,
            )

            await asyncio.sleep(UPDATE_DELAY_AFTER_COMMAND)
            await self.coordinator.async_refresh_device(self.device_id)

        except RuntimeError as err:
            _LOGGER.error("Error setting temperature for %s: %s", self._attr_name, err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        mode = HVAC_MODE_TO_THERMOSTAT.get(hvac_mode)
        if mode is None:
            _LOGGER.error("Unsupported HVAC mode %s for %s", hvac_mode, self._attr_name)
            return

        try:
            await self.coordinator.client.set_thermostat_mode(self.device_id, mode)
            _LOGGER.debug(
                "Successfully set HVAC mode to %s (ThermostatMode.%s) for %s",
                hvac_mode,
                mode.name,
                self._attr_name,
            )

            await asyncio.sleep(UPDATE_DELAY_AFTER_COMMAND)
            await self.coordinator.async_refresh_device(self.device_id)

        except (ValueError, RuntimeError) as err:
            _LOGGER.error("Error setting HVAC mode for %s: %s", self._attr_name, err)
