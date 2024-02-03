"""Platform for eQ-3 climate entities."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from eq3btsmart import Thermostat
from eq3btsmart.const import EQ3BT_MAX_TEMP, EQ3BT_OFF_TEMP, Eq3Preset, OperationMode
from eq3btsmart.exceptions import Eq3Exception

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    async_get,
    format_mac,
)
from homeassistant.helpers.entity import Entity, EntityPlatformState
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    DEVICE_MODEL,
    DOMAIN,
    EQ_TO_HA_HVAC,
    HA_TO_EQ_HVAC,
    MANUFACTURER,
    CurrentTemperatureSelector,
    Preset,
    TargetTemperatureSelector,
)
from .eq3_entity import Eq3Entity
from .models import Eq3Config, Eq3ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Handle config entry setup."""

    eq3_config_entry: Eq3ConfigEntry = hass.data[DOMAIN][config_entry.entry_id]
    thermostat = eq3_config_entry.thermostat
    eq3_config = eq3_config_entry.eq3_config

    entities_to_add: list[Entity] = [Eq3Climate(eq3_config, thermostat)]

    async_add_entities(
        entities_to_add,
        update_before_add=False,
    )


class Eq3Climate(Eq3Entity, ClimateEntity):
    """Climate entity to represent a eQ-3 thermostat."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the climate entity."""

        super().__init__(eq3_config, thermostat)

        self._thermostat.register_update_callback(self._on_updated)
        self._thermostat.register_connection_callback(self._on_connection_changed)
        self._target_temperature: float | None = None
        self._is_available = False
        self._cancel_timer: Callable[[], None] | None = None
        self._attr_has_entity_name = True
        self._attr_name = None
        self._attr_hvac_mode = None
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_TENTHS
        self._attr_hvac_modes = list(HA_TO_EQ_HVAC.keys())
        self._attr_min_temp = EQ3BT_OFF_TEMP
        self._attr_max_temp = EQ3BT_MAX_TEMP
        self._attr_preset_modes = list(Preset)
        self._attr_unique_id = format_mac(self._eq3_config.mac_address)
        self._attr_should_poll = False
        self._was_connected: bool = False
        self._firmware_version: str | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        asyncio.get_event_loop().create_task(self._async_scan_loop())
        self._on_connection_changed(True)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""

        if self._cancel_timer:
            self._cancel_timer()

    async def _async_scan_loop(self, now: datetime | None = None) -> None:
        """Scan for data."""

        await self.async_scan()

        if self._platform_state != EntityPlatformState.REMOVED:
            delay = timedelta(seconds=self._eq3_config.scan_interval)
            self._cancel_timer = async_call_later(
                self.hass, delay, self._async_scan_loop
            )

    @callback
    def _on_updated(self) -> None:
        """Handle updated data from the thermostat."""

        self._is_available = True

        if self._thermostat.status is not None:
            self._on_status_updated()

        if self._thermostat.device_data is not None:
            self._on_device_updated()

        self.schedule_update_ha_state()

    @callback
    def _on_status_updated(self) -> None:
        """Handle updated status from the thermostat."""

        self._target_temperature = self._thermostat.status.target_temperature.value
        self._attr_hvac_mode = EQ_TO_HA_HVAC[self._thermostat.status.operation_mode]

    @callback
    def _on_device_updated(self) -> None:
        """Handle updated device data from the thermostat."""

        self._firmware_version = str(self._thermostat.device_data.firmware_version)

        device_registry = async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._eq3_config.mac_address)},
        )

        if device:
            device_registry.async_update_device(
                device_id=device.id,
                sw_version=self._firmware_version,
            )

    @callback
    def _on_connection_changed(self, is_connected: bool = True) -> None:
        """Handle connection changed."""

        self._is_available = is_connected

        if is_connected and not self._was_connected:
            _LOGGER.info("[%s] Connected", self._eq3_config.name)
            self._was_connected = True
            self.hass.add_job(self._update_device())

        if not is_connected and self._was_connected:
            _LOGGER.warning("[%s] Disconnected", self._eq3_config.name)
            self._was_connected = False

        self.schedule_update_ha_state()

    @callback
    async def _update_device(self) -> None:
        try:
            await self._thermostat.async_get_id()
        except Eq3Exception:
            _LOGGER.error(
                "[%s] Error fetching device information", self._eq3_config.name
            )
            return

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return self._is_available

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""

        if self._thermostat.status is None:
            return None

        if self._thermostat.status.operation_mode == OperationMode.OFF:
            return HVACAction.OFF

        if self._thermostat.status.valve == 0:
            return HVACAction.IDLE

        return HVACAction.HEATING

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""

        match self._eq3_config.current_temp_selector:
            case CurrentTemperatureSelector.NOTHING:
                return None
            case CurrentTemperatureSelector.VALVE:
                if self._thermostat.status is None:
                    return None

                return float(self._thermostat.status.valve_temperature)
            case CurrentTemperatureSelector.UI:
                return self._target_temperature
            case CurrentTemperatureSelector.DEVICE:
                if self._thermostat.status is None:
                    return None

                return float(self._thermostat.status.target_temperature.value)
            case CurrentTemperatureSelector.ENTITY:
                state = self.hass.states.get(self._eq3_config.external_temp_sensor)
                if state is not None:
                    try:
                        return float(state.state)
                    except ValueError:
                        pass

        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""

        match self._eq3_config.target_temp_selector:
            case TargetTemperatureSelector.TARGET:
                return self._target_temperature
            case TargetTemperatureSelector.LAST_REPORTED:
                if self._thermostat.status is None:
                    return None

                return float(self._thermostat.status.target_temperature.value)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""

        if ATTR_HVAC_MODE in kwargs:
            mode = kwargs.get(ATTR_HVAC_MODE)

            if mode is None:
                return

            if mode == HVACMode.OFF:
                raise ServiceValidationError(
                    f"[{self._eq3_config.name}] Can't change HVAC mode to off while changing temperature",
                )

            await self.async_set_hvac_mode(mode)

        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return

        temperature = round(temperature * 2) / 2
        temperature = min(temperature, self.max_temp)
        temperature = max(temperature, self.min_temp)

        previous_temperature = self._target_temperature
        self._target_temperature = temperature

        self.async_schedule_update_ha_state()

        try:
            await self._thermostat.async_set_temperature(self._target_temperature)
        except Eq3Exception:
            _LOGGER.error("[%s] Failed setting temperature", self._eq3_config.name)
            self._target_temperature = previous_temperature
            self.async_schedule_update_ha_state()
        except ValueError as ex:
            raise ServiceValidationError("Invalid temperature") from ex

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""

        return self._attr_hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if hvac_mode == HVACMode.OFF:
            self._target_temperature = EQ3BT_OFF_TEMP
            await self.async_set_temperature(temperature=EQ3BT_OFF_TEMP)

        previous_mode = self.hvac_mode
        self._attr_hvac_mode = hvac_mode

        self.async_schedule_update_ha_state()

        try:
            await self._thermostat.async_set_mode(HA_TO_EQ_HVAC[hvac_mode])
        except Eq3Exception:
            _LOGGER.error("[%s] Failed setting HVAC mode", self._eq3_config.name)
            self._attr_hvac_mode = previous_mode

        self.async_schedule_update_ha_state()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""

        if self._thermostat.status is None:
            return None

        if self._thermostat.status.is_window_open:
            return Preset.WINDOW_OPEN
        if self._thermostat.status.is_boost:
            return Preset.BOOST
        if self._thermostat.status.is_low_battery:
            return Preset.LOW_BATTERY
        if self._thermostat.status.is_away:
            return Preset.AWAY
        if self._thermostat.status.operation_mode == OperationMode.ON:
            return Preset.OPEN

        if self._thermostat.status.presets is None:
            return None

        if (
            self._thermostat.status.target_temperature
            == self._thermostat.status.presets.eco_temperature
        ):
            return Preset.ECO
        if (
            self._thermostat.status.target_temperature
            == self._thermostat.status.presets.comfort_temperature
        ):
            return Preset.COMFORT
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        match preset_mode:
            case Preset.BOOST:
                await self._thermostat.async_set_boost(True)
            case Preset.AWAY:
                await self._thermostat.async_set_away(True)
            case Preset.ECO:
                await self._thermostat.async_set_preset(Eq3Preset.ECO)
            case Preset.COMFORT:
                await self._thermostat.async_set_preset(Eq3Preset.COMFORT)
            case Preset.OPEN:
                await self._thermostat.async_set_mode(OperationMode.ON)

        if self._thermostat.status is not None:
            self._target_temperature = self._thermostat.status.target_temperature.value

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""

        return DeviceInfo(
            name=self._eq3_config.name,
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            identifiers={(DOMAIN, self._eq3_config.mac_address)},
            sw_version=self._firmware_version,
            connections={(CONNECTION_BLUETOOTH, self._eq3_config.mac_address)},
        )

    async def async_scan(self) -> None:
        """Update the data from the thermostat."""

        try:
            await self._thermostat.async_get_status()
        except Eq3Exception:
            self._is_available = False
            self.schedule_update_ha_state()
