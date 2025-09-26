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

    coordinator: WattsVisionCoordinator = entry.runtime_data["coordinator"]

    entities = []
    for device in coordinator.data.values():
        if isinstance(device, ThermostatDevice):
            entities.append(WattsVisionClimate(coordinator, device))
            _LOGGER.debug("Created climate entity for device %s", device.device_id)

    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Added %d climate entities", len(entities))


class WattsVisionClimate(WattsVisionEntity, ClimateEntity):
    """Representation of a Watts Vision heater as a climate entity."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]

    def __init__(
        self,
        coordinator: WattsVisionCoordinator,
        device: ThermostatDevice,
    ) -> None:
        """Initialize the climate entity."""

        super().__init__(coordinator, device.device_id)
        self._device = device
        self._device_id = device.device_id

        self._attr_name = None

        self._attr_min_temp = device.min_allowed_temperature
        self._attr_max_temp = device.max_allowed_temperature

        if device.temperature_unit.upper() == "C":
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        else:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        device = self.coordinator.data.get(self._device_id)
        if isinstance(device, ThermostatDevice):
            return device.current_temperature
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature setpoint."""
        device = self.coordinator.data.get(self._device_id)
        if isinstance(device, ThermostatDevice):
            return device.setpoint
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        device = self.coordinator.data.get(self._device_id)
        if isinstance(device, ThermostatDevice):
            return THERMOSTAT_MODE_TO_HVAC.get(device.thermostat_mode)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device = self.coordinator.data.get(self._device_id)
        if not isinstance(device, ThermostatDevice):
            return {}

        return {
            "thermostat_mode": device.thermostat_mode,
            "device_type": device.device_type,
            "room_name": device.room_name,
            "temperature_unit": device.temperature_unit,
            "available_thermostat_modes": device.available_thermostat_modes,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self.coordinator.client.set_thermostat_temperature(
                self._device_id, temperature
            )
            _LOGGER.debug(
                "Successfully set temperature to %s for %s",
                temperature,
                self._attr_name,
            )

            await asyncio.sleep(UPDATE_DELAY_AFTER_COMMAND)
            await self.coordinator.async_refresh_device(self._device_id)

        except RuntimeError as err:
            _LOGGER.error("Error setting temperature for %s: %s", self._attr_name, err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        mode = HVAC_MODE_TO_THERMOSTAT.get(hvac_mode)
        if mode is None:
            _LOGGER.error("Unsupported HVAC mode %s for %s", hvac_mode, self._attr_name)
            return

        try:
            await self.coordinator.client.set_thermostat_mode(self._device_id, mode)
            _LOGGER.debug(
                "Successfully set HVAC mode to %s (ThermostatMode.%s) for %s",
                hvac_mode,
                mode.name,
                self._attr_name,
            )

            await asyncio.sleep(UPDATE_DELAY_AFTER_COMMAND)
            await self.coordinator.async_refresh_device(self._device_id)

        except (ValueError, RuntimeError) as err:
            _LOGGER.error("Error setting HVAC mode for %s: %s", self._attr_name, err)
