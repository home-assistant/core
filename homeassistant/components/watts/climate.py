"""Climate platform for Watts Vision integration."""

from __future__ import annotations

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WattsVisionConfigEntry
from .const import HVAC_MODE_TO_THERMOSTAT, THERMOSTAT_MODE_TO_HVAC
from .coordinator import WattsVisionDeviceCoordinator
from .entity import WattsVisionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattsVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Watts Vision climate entities from a config entry."""

    device_coordinators = entry.runtime_data.device_coordinators

    async_add_entities(
        WattsVisionClimate(device_coordinator, device_coordinator.data)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.data
    )


class WattsVisionClimate(WattsVisionEntity, ClimateEntity):
    """Representation of a Watts Vision heater as a climate entity."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_name = None

    def __init__(
        self,
        coordinator: WattsVisionDeviceCoordinator,
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
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature setpoint."""
        return self.device.setpoint

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac mode."""
        return THERMOSTAT_MODE_TO_HVAC.get(self.device.thermostat_mode)

    async def async_request_refresh(self) -> None:
        """Request refresh for this specific entity only."""
        await self.coordinator.async_refresh()

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
                self.device_id,
            )

            self.coordinator.trigger_fast_polling()

            await self.coordinator.async_refresh()

        except RuntimeError as err:
            raise HomeAssistantError(
                f"Error setting temperature for {self.device_id}: {err}"
            ) from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        mode = HVAC_MODE_TO_THERMOSTAT[hvac_mode]

        try:
            await self.coordinator.client.set_thermostat_mode(self.device_id, mode)
            _LOGGER.debug(
                "Successfully set HVAC mode to %s (ThermostatMode.%s) for %s",
                hvac_mode,
                mode.name,
                self.device_id,
            )

            self.coordinator.trigger_fast_polling()

        except (ValueError, RuntimeError) as err:
            raise HomeAssistantError(
                f"Error setting HVAC mode for {self.device_id}: {err}"
            ) from err

        await self.coordinator.async_refresh()
