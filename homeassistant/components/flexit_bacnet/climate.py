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
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FlexitDataUpdateCoordinator
from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    NAME,
    PRESET_TO_VENTILATION_MODE_MAP,
    VENTILATION_TO_PRESET_MODE_MAP,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flexit Nordic unit."""
    data_coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([FlexitClimateEntity(data_coordinator)])


class FlexitClimateEntity(CoordinatorEntity, ClimateEntity):
    """Flexit air handling unit."""

    _attr_has_entity_name = True

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
        | ClimateEntityFeature.AUX_HEAT
    )

    _attr_target_temperature_step = 1.0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: FlexitDataUpdateCoordinator,
    ) -> None:
        """Initialize the unit."""
        super().__init__(coordinator)
        self._flexit_bacnet = coordinator.flexit_bacnet
        self._attr_unique_id = f"{self._flexit_bacnet.serial_number}-climate"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.flexit_bacnet.serial_number),
            },
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def name(self) -> str:
        """Name of the entity."""
        return self._flexit_bacnet.device_name

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._flexit_bacnet.room_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if self._flexit_bacnet.ventilation_mode == VENTILATION_MODE_AWAY:
            return self._flexit_bacnet.air_temp_setpoint_away

        return self._flexit_bacnet.air_temp_setpoint_home

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        try:
            if self._flexit_bacnet.ventilation_mode == VENTILATION_MODE_AWAY:
                await self._flexit_bacnet.set_air_temp_setpoint_away(temperature)
            else:
                await self._flexit_bacnet.set_air_temp_setpoint_home(temperature)
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return VENTILATION_TO_PRESET_MODE_MAP[self._flexit_bacnet.ventilation_mode]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        ventilation_mode = PRESET_TO_VENTILATION_MODE_MAP[preset_mode]

        try:
            await self._flexit_bacnet.set_ventilation_mode(ventilation_mode)
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self._flexit_bacnet.ventilation_mode == VENTILATION_MODE_STOP:
            return HVACMode.OFF

        return HVACMode.FAN_ONLY

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                await self._flexit_bacnet.set_ventilation_mode(VENTILATION_MODE_STOP)
            else:
                await self._flexit_bacnet.set_ventilation_mode(VENTILATION_MODE_HOME)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    @property
    def is_aux_heat(self) -> bool:
        """Return true if aux heater.

        Requires ClimateEntityFeature.AUX_HEAT.
        """
        return self._flexit_bacnet.electric_heater

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        try:
            await self._flexit_bacnet.enable_electric_heater()
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        try:
            await self._flexit_bacnet.disable_electric_heater()
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError from exc
