"""The Flexit Nordic (BACnet) integration."""

import asyncio.exceptions
from typing import Any

from flexit_bacnet import (
    VENTILATION_MODE_AWAY,
    VENTILATION_MODE_HOME,
    VENTILATION_MODE_STOP,
)
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_TO_VENTILATION_MODE_MAP,
    VENTILATION_TO_PRESET_MODE_MAP,
)
from .coordinator import FlexitCoordinator
from .entity import FlexitEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flexit Nordic unit."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([FlexitClimateEntity(coordinator)])


class FlexitClimateEntity(FlexitEntity, ClimateEntity):
    """Flexit air handling unit."""

    _attr_name = None

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.FAN_ONLY,
    ]

    _attr_preset_modes = [
        PRESET_AWAY,
        PRESET_HOME,
        PRESET_BOOST,
    ]

    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = MAX_TEMP
    _attr_min_temp = MIN_TEMP
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: FlexitCoordinator) -> None:
        """Initialize the Flexit unit."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device.serial_number

    async def async_update(self) -> None:
        """Refresh unit state."""
        await self.device.update()

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        if self.device.electric_heater:
            return HVACAction.HEATING
        return HVACAction.FAN

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.device.room_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if self.device.ventilation_mode == VENTILATION_MODE_AWAY:
            return self.device.air_temp_setpoint_away

        return self.device.air_temp_setpoint_home

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        try:
            if self.device.ventilation_mode == VENTILATION_MODE_AWAY:
                await self.device.set_air_temp_setpoint_away(temperature)
            else:
                await self.device.set_air_temp_setpoint_home(temperature)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await self.coordinator.async_refresh()

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return VENTILATION_TO_PRESET_MODE_MAP[self.device.ventilation_mode]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        ventilation_mode = PRESET_TO_VENTILATION_MODE_MAP[preset_mode]

        try:
            await self.device.set_ventilation_mode(ventilation_mode)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await self.coordinator.async_refresh()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self.device.ventilation_mode == VENTILATION_MODE_STOP:
            return HVACMode.OFF

        return HVACMode.FAN_ONLY

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                await self.device.set_ventilation_mode(VENTILATION_MODE_STOP)
            else:
                await self.device.set_ventilation_mode(VENTILATION_MODE_HOME)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
        finally:
            await self.coordinator.async_refresh()
