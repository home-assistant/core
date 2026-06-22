"""Support for Schluter DITRA-HEAT thermostats."""

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CannotConnectError, InvalidSessionError, SchluterThermostat
from .const import DOMAIN
from .coordinator import SchluterConfigEntry, SchluterCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchluterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Schluter thermostat entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        SchluterThermostatEntity(coordinator, serial_number)
        for serial_number in coordinator.data
    )


class SchluterThermostatEntity(CoordinatorEntity[SchluterCoordinator], ClimateEntity):
    """Climate entity for a single Schluter DITRA-HEAT thermostat."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: SchluterCoordinator, serial_number: str) -> None:
        """Initialize the thermostat entity."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._attr_unique_id = serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=coordinator.data[serial_number].name,
            manufacturer="Schluter",
            model="DITRA-HEAT-E-Wi-Fi",
            serial_number=serial_number,
            sw_version=coordinator.data[serial_number].sw_version,
        )

    @property
    def _thermostat(self) -> SchluterThermostat:
        return self.coordinator.data[self._serial_number]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._thermostat.temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._thermostat.set_point_temp

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._thermostat.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._thermostat.max_temp

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action; can only be heating or idle."""
        if self._thermostat.is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """HVAC mode is always HEAT for floor heating; nothing to do."""

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        try:
            await self.coordinator.api.async_set_temperature(
                self.coordinator.session_id,
                self._serial_number,
                temperature,
            )
        except (InvalidSessionError, CannotConnectError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
            ) from err
        finally:
            await self.coordinator.async_request_refresh()
