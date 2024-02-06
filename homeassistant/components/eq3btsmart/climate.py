"""Platform for eQ-3 climate entities."""

from collections.abc import Callable
import logging
from typing import Any

from eq3btsmart import Thermostat
from eq3btsmart.const import EQ3BT_MAX_TEMP, EQ3BT_OFF_TEMP, Eq3Preset, OperationMode
from eq3btsmart.exceptions import Eq3Exception
from voluptuous import FalseInvalid

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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_MODEL,
    DOMAIN,
    EQ_TO_HA_HVAC,
    HA_TO_EQ_HVAC,
    MANUFACTURER,
    SIGNAL_THERMOSTAT_CONNECTED,
    SIGNAL_THERMOSTAT_DISCONNECTED,
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

    async_add_entities(
        [Eq3Climate(eq3_config_entry.eq3_config, eq3_config_entry.thermostat)],
        update_before_add=False,
    )


class Eq3Climate(Eq3Entity, ClimateEntity):
    """Climate entity to represent a eQ-3 thermostat."""

    def __init__(self, eq3_config: Eq3Config, thermostat: Thermostat) -> None:
        """Initialize the climate entity."""

        super().__init__(eq3_config, thermostat)

        self._thermostat.register_update_callback(self._async_on_updated)
        self._target_temperature: float | None = None
        self._attr_available = False
        self._cancel_timer: Callable[[], None] | None = None
        self._attr_has_entity_name = True
        self._attr_name = None
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_TENTHS
        self._attr_hvac_mode: HVACMode | None = None
        self._attr_hvac_action: HVACAction | None = None
        self._attr_preset_mode: str | None = None
        self._attr_hvac_modes = list(HA_TO_EQ_HVAC.keys())
        self._attr_min_temp = EQ3BT_OFF_TEMP
        self._attr_max_temp = EQ3BT_MAX_TEMP
        self._attr_preset_modes = list(Preset)
        self._attr_unique_id = format_mac(self._eq3_config.mac_address)
        self._attr_should_poll = FalseInvalid
        self._attr_device_info: DeviceInfo = DeviceInfo(
            name=self._eq3_config.name,
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            sw_version=None,
            serial_number=None,
            connections={(CONNECTION_BLUETOOTH, self._eq3_config.mac_address)},
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        async_dispatcher_connect(
            self.hass, SIGNAL_THERMOSTAT_DISCONNECTED, self._async_on_disconnected
        )
        async_dispatcher_connect(
            self.hass, SIGNAL_THERMOSTAT_CONNECTED, self._async_on_connected
        )

    @callback
    def _async_on_disconnected(self, mac_address: str) -> None:
        if mac_address == self._eq3_config.mac_address:
            self._attr_available = False
            self.async_schedule_update_ha_state(force_refresh=True)

    @callback
    def _async_on_connected(self, mac_address: str) -> None:
        if mac_address == self._eq3_config.mac_address:
            self._attr_available = True
            self.async_schedule_update_ha_state(force_refresh=True)

    @callback
    def _async_on_updated(self) -> None:
        """Handle updated data from the thermostat."""

        if self._thermostat.status is not None:
            self._async_on_status_updated()

        if self._thermostat.device_data is not None:
            self._async_on_device_updated()

        self.async_schedule_update_ha_state()

    @callback
    def _async_on_status_updated(self) -> None:
        """Handle updated status from the thermostat."""

        self._target_temperature = self._thermostat.status.target_temperature.value
        self._attr_hvac_mode = EQ_TO_HA_HVAC[self._thermostat.status.operation_mode]

        if self._thermostat.status.operation_mode is OperationMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif self._thermostat.status.valve == 0:
            self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_action = HVACAction.HEATING

        if self._thermostat.status.is_window_open:
            self._attr_preset_mode = Preset.WINDOW_OPEN
        elif self._thermostat.status.is_boost:
            self._attr_preset_mode = Preset.BOOST
        elif self._thermostat.status.is_low_battery:
            self._attr_preset_mode = Preset.LOW_BATTERY
        elif self._thermostat.status.is_away:
            self._attr_preset_mode = Preset.AWAY
        elif self._thermostat.status.operation_mode is OperationMode.ON:
            self._attr_preset_mode = Preset.OPEN
        elif self._thermostat.status.presets is None:
            self._attr_preset_mode = PRESET_NONE
        elif (
            self._thermostat.status.target_temperature
            == self._thermostat.status.presets.eco_temperature
        ):
            self._attr_preset_mode = Preset.ECO
        elif (
            self._thermostat.status.target_temperature
            == self._thermostat.status.presets.comfort_temperature
        ):
            self._attr_preset_mode = Preset.COMFORT
        else:
            self._attr_preset_mode = PRESET_NONE

    @callback
    def _async_on_device_updated(self) -> None:
        """Handle updated device data from the thermostat."""

        device_registry = async_get(self.hass)
        if device := device_registry.async_get_device(
            connections={(CONNECTION_BLUETOOTH, self._eq3_config.mac_address)},
        ):
            device_registry.async_update_device(
                device.id,
                sw_version=self._thermostat.device_data.firmware_version,
                serial_number=self._thermostat.device_data.device_serial.value,
            )

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
