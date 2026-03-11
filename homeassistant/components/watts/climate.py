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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WattsVisionConfigEntry
from .const import DOMAIN, HVAC_MODE_TO_THERMOSTAT, THERMOSTAT_MODE_TO_HVAC
from .coordinator import WattsVisionDeviceCoordinator
from .entity import WattsVisionEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattsVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Watts Vision climate entities from a config entry."""
    device_coordinators = entry.runtime_data.device_coordinators
    known_device_ids: set[str] = set()

    @callback
    def _check_new_thermostats() -> None:
        """Check for new thermostat devices."""
        thermostat_coords = {
            did: coord
            for did, coord in device_coordinators.items()
            if isinstance(coord.data.device, ThermostatDevice)
        }
        current_device_ids = set(thermostat_coords.keys())
        new_device_ids = current_device_ids - known_device_ids

        if not new_device_ids:
            return

        _LOGGER.debug(
            "Adding climate entities for %d new thermostat(s)",
            len(new_device_ids),
        )

        new_entities = []
        for device_id in new_device_ids:
            coord = thermostat_coords[device_id]
            device = coord.data.device
            assert isinstance(device, ThermostatDevice)
            new_entities.append(WattsVisionClimate(coord, device))

        known_device_ids.update(new_device_ids)
        async_add_entities(new_entities)

    _check_new_thermostats()

    # Listen for new thermostats
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_new_device",
            _check_new_thermostats,
        )
    )


class WattsVisionClimate(WattsVisionEntity[ThermostatDevice], ClimateEntity):
    """Representation of a Watts Vision heater as a climate entity."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_name = None

    def __init__(
        self,
        coordinator: WattsVisionDeviceCoordinator,
        thermostat: ThermostatDevice,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, thermostat.device_id)

        self._attr_min_temp = thermostat.min_allowed_temperature
        self._attr_max_temp = thermostat.max_allowed_temperature

        if thermostat.temperature_unit.upper() == "C":
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self.coordinator.client.set_thermostat_temperature(
                self.device_id, temperature
            )
        except RuntimeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_error",
            ) from err

        _LOGGER.debug(
            "Successfully set temperature to %s for %s",
            temperature,
            self.device_id,
        )

        self.coordinator.trigger_fast_polling()

        await self.coordinator.async_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        mode = HVAC_MODE_TO_THERMOSTAT[hvac_mode]

        try:
            await self.coordinator.client.set_thermostat_mode(self.device_id, mode)
        except (ValueError, RuntimeError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_hvac_mode_error",
            ) from err

        _LOGGER.debug(
            "Successfully set HVAC mode to %s (ThermostatMode.%s) for %s",
            hvac_mode,
            mode.name,
            self.device_id,
        )

        self.coordinator.trigger_fast_polling()

        await self.coordinator.async_refresh()
