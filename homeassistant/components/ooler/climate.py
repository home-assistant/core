"""Support for Ooler Sleep System controls."""
from __future__ import annotations

from asyncio import sleep
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import _LOGGER, DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN
from .models import OolerData

IGNORED_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}

SERVICE_PAUSE = "pause_service"
SERVICE_CLEAN = "clean_service"
SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ooler thermostat."""
    data: OolerData = hass.data[DOMAIN][config_entry.entry_id]
    entities = [Ooler(data)]
    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_PAUSE,
        {},
        "async_pause_client",
    )
    platform.async_register_entity_service(
        SERVICE_CLEAN,
        {},
        "async_set_clean",
    )


class Ooler(ClimateEntity, RestoreEntity):
    """Representation of Ooler Thermostat."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_target_temperature_step = 1
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_max_temp = DEFAULT_MAX_TEMP

    def __init__(self, data: OolerData) -> None:
        """Initialize the climate entity."""
        self._data = data
        self._attr_unique_id = f"ooler_{data.address}_thermostat"
        self._attr_device_info = DeviceInfo(
            name=data.model, connections={(dr.CONNECTION_BLUETOOTH, data.address)}
        )
        self._operation_list: list[HVACMode] = [HVACMode.OFF, HVACMode.AUTO]
        self._fan_modes: list[str] = ["Silent", "Regular", "Boost"]
        self._attr_support_flags = SUPPORT_FLAGS
        super().__init__()

    @property
    def name(self) -> str | None:
        """Return entity name."""
        return self._attr_name

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return self._data.client.is_connected

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return self._attr_temperature_unit

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature."""
        return self._attr_min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature."""
        return self._attr_max_temp

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._attr_target_temperature_step

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature we try to reach."""
        return self._data.client.state.set_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._data.client.state.actual_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._data.client.state.mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the fan modes list."""
        return self._fan_modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation."""
        if self._data.client.state.power:
            return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the operation modes list."""
        return self._operation_list

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action (heating, cooling)."""
        hvacmode = self.hvac_mode
        if hvacmode == HVACMode.OFF:
            return HVACAction.OFF
        settemp = self.target_temperature
        currenttemp = self.current_temperature
        if currenttemp is not None and settemp is not None:
            if currenttemp > settemp:
                return HVACAction.COOLING
            if currenttemp < settemp:
                return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return self._attr_support_flags

    @property
    def cleaning(self) -> bool | None:
        """Return if the unit is cleaning itself."""
        return self._data.client.state.clean

    @callback
    def _handle_state_update(self, *args: Any) -> None:
        """Handle state update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state on start up and register callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._data.client.register_callback(self._handle_state_update)
        )

    async def async_update(self) -> None:
        """Grab the state from device and update HA."""
        await self._data.client.async_poll()
        self._async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVACMode (On/Off)."""
        if hvac_mode == HVACMode.OFF:
            power = False
        else:
            power = True
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()
        await client.set_power(power)
        _LOGGER.info("Setting HVACMode to: %s", hvac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode. Valid values are Silent, Regular, and Boost."""
        if fan_mode not in self._fan_modes:
            error = "Invalid fan_mode value: Valid values are 'Silent', 'Regular', and 'Boost'"
            _LOGGER.error(error)
            return
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()
        await client.set_mode(fan_mode)
        _LOGGER.info("Setting fan mode to: %s", fan_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            raise ValueError("No target temperature provided.")
        if temp == self.target_temperature:
            return
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()
        await client.set_temperature(int(temp))
        _LOGGER.info("Setting temperature to :%s", temp)

    async def async_set_clean(self) -> None:
        """Start cleaning the unit."""
        client = self._data.client
        if not client.is_connected:
            _LOGGER.debug("Client not connected. Attempting to connect")
            await client.connect()
        await client.set_clean(True)
        _LOGGER.info("Cleaning the device: %s", self.name)

    # This service function is necessary because the Bluetooth connection is active, which means when Hass is connected to Ooler, nothing else can connect to Ooler including the phone app.
    async def async_pause_client(self, sec_delay: int = 60) -> None:
        """Disconnect Hass from the device."""
        await self._data.client.stop()
        await sleep(sec_delay)
        await self._data.client.connect()
