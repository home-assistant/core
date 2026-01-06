"""Climate platform for Airobot thermostat."""

from __future__ import annotations

from typing import Any

from pyairobotrest.const import (
    MODE_AWAY,
    MODE_HOME,
    SETPOINT_TEMP_MAX,
    SETPOINT_TEMP_MIN,
)
from pyairobotrest.exceptions import AirobotError
from pyairobotrest.models import ThermostatSettings, ThermostatStatus

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirobotConfigEntry
from .const import DOMAIN
from .entity import AirobotEntity

PARALLEL_UPDATES = 1

_PRESET_MODE_2_MODE = {
    PRESET_AWAY: MODE_AWAY,
    PRESET_HOME: MODE_HOME,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot climate platform."""
    coordinator = entry.runtime_data
    async_add_entities([AirobotClimate(coordinator)])


class AirobotClimate(AirobotEntity, ClimateEntity):
    """Representation of an Airobot thermostat."""

    _attr_name = None
    _attr_translation_key = "thermostat"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = [PRESET_HOME, PRESET_AWAY, PRESET_BOOST]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_min_temp = SETPOINT_TEMP_MIN
    _attr_max_temp = SETPOINT_TEMP_MAX

    @property
    def _status(self) -> ThermostatStatus:
        """Get status from coordinator data."""
        return self.coordinator.data.status

    @property
    def _settings(self) -> ThermostatSettings:
        """Get settings from coordinator data."""
        return self.coordinator.data.settings

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature.

        If floor temperature is available, thermostat is set up for floor heating.
        """
        if self._status.temp_floor is not None:
            return self._status.temp_floor
        return self._status.temp_air

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._status.hum_air

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self._settings.is_home_mode:
            return self._settings.setpoint_temp
        return self._settings.setpoint_temp_away

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self._status.is_heating:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if self._status.is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        if self._settings.setting_flags.boost_enabled:
            return PRESET_BOOST
        if self._settings.is_home_mode:
            return PRESET_HOME
        return PRESET_AWAY

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        try:
            if self._settings.is_home_mode:
                await self.coordinator.client.set_home_temperature(float(temperature))
            else:
                await self.coordinator.client.set_away_temperature(float(temperature))
        except AirobotError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
                translation_placeholders={"temperature": str(temperature)},
            ) from err

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode.

        This thermostat only supports HEAT mode. The climate platform validates
        that only supported modes are passed, so this method is a no-op.
        """

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            if preset_mode == PRESET_BOOST:
                # Enable boost mode
                if not self._settings.setting_flags.boost_enabled:
                    await self.coordinator.client.set_boost_mode(True)
            else:
                # Disable boost mode if it's enabled
                if self._settings.setting_flags.boost_enabled:
                    await self.coordinator.client.set_boost_mode(False)

                # Set the mode (HOME or AWAY)
                await self.coordinator.client.set_mode(_PRESET_MODE_2_MODE[preset_mode])

        except AirobotError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_preset_mode_failed",
                translation_placeholders={"preset_mode": preset_mode},
            ) from err

        await self.coordinator.async_request_refresh()
