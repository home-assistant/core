"""Support for Google Nest SDM climate devices."""

from asyncio import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import FanTrait, HumidityTrait, TemperatureTrait
from google_nest_sdm.exceptions import ApiException
from google_nest_sdm.thermostat_traits import (
    ThermostatEcoTrait,
    ThermostatHvacTrait,
    ThermostatModeTrait,
    ThermostatTemperatureSetpointTrait,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_OFF,
    FAN_ON,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .device_info import NestDeviceInfo
from .types import NestConfigEntry

_LOGGER = logging.getLogger(__name__)

# Mapping for sdm.devices.traits.ThermostatMode mode field
THERMOSTAT_MODE_MAP: dict[str, HVACMode] = {
    "OFF": HVACMode.OFF,
    "HEAT": HVACMode.HEAT,
    "COOL": HVACMode.COOL,
    "HEATCOOL": HVACMode.HEAT_COOL,
}
THERMOSTAT_INV_MODE_MAP = {v: k for k, v in THERMOSTAT_MODE_MAP.items()}

# Mode for sdm.devices.traits.ThermostatEco
THERMOSTAT_ECO_MODE = "MANUAL_ECO"

# Mapping for sdm.devices.traits.ThermostatHvac status field
THERMOSTAT_HVAC_STATUS_MAP = {
    "OFF": HVACAction.OFF,
    "HEATING": HVACAction.HEATING,
    "COOLING": HVACAction.COOLING,
}

THERMOSTAT_RANGE_MODES = [HVACMode.HEAT_COOL, HVACMode.AUTO]

PRESET_MODE_MAP = {
    "MANUAL_ECO": PRESET_ECO,
    "OFF": PRESET_NONE,
}
PRESET_INV_MODE_MAP = {v: k for k, v in PRESET_MODE_MAP.items()}

FAN_MODE_MAP = {
    "ON": FAN_ON,
    "OFF": FAN_OFF,
}
FAN_INV_MODE_MAP = {v: k for k, v in FAN_MODE_MAP.items()}
FAN_INV_MODES = list(FAN_INV_MODE_MAP)

MAX_FAN_DURATION = 43200  # 12 hours is the max in the SDM API
MIN_TEMP = 10
MAX_TEMP = 32
MIN_TEMP_RANGE = 1.66667
# Avoid Google's aggressive API rate limits when making incremental adjustments.
TEMPERATURE_DEBOUNCE_SECONDS = 10
TEMPERATURE_PENDING_TIMEOUT_SECONDS = 10


@dataclass
class _PendingTemperature:
    """A temperature command pending delivery or expiration."""

    kwargs: dict[str, Any]
    hvac_mode: HVACMode
    sent: bool = False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the client entities."""

    def devices_added(devices: list[Device]) -> None:
        async_add_entities(
            ThermostatEntity(device)
            for device in devices
            if ThermostatHvacTrait.NAME in device.traits
        )

    entry.runtime_data.register_devices_listener(devices_added)


class ThermostatEntity(ClimateEntity):
    """A nest thermostat climate entity."""

    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Initialize ThermostatEntity."""
        self._device = device
        self._device_info = NestDeviceInfo(device)
        # The API "name" field is a unique device identifier.
        self._attr_unique_id = device.name
        self._attr_device_info = self._device_info.device_info
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._command_lock = Lock()
        self._pending_temperature: _PendingTemperature | None = None
        if mode_trait := device.traits.get(ThermostatModeTrait.NAME):
            self._attr_hvac_modes = [
                THERMOSTAT_MODE_MAP[mode]
                for mode in mode_trait.available_modes
                if mode in THERMOSTAT_MODE_MAP
            ]
        else:
            self._attr_hvac_modes = []

    @property
    @override
    def available(self) -> bool:
        """Return device availability."""
        return self._device_info.available

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self._attr_supported_features = self._get_supported_features()
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )
        self.async_on_remove(lambda: setattr(self, "_pending_temperature", None))

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if TemperatureTrait.NAME not in self._device.traits:
            return None
        trait: TemperatureTrait = self._device.traits[TemperatureTrait.NAME]
        return trait.ambient_temperature_celsius

    @property
    @override
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        if HumidityTrait.NAME not in self._device.traits:
            return None
        trait: HumidityTrait = self._device.traits[HumidityTrait.NAME]
        return trait.ambient_humidity_percent

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        temperature = self._pending_temperature
        if temperature and ATTR_TEMPERATURE in temperature.kwargs:
            return cast(float, temperature.kwargs[ATTR_TEMPERATURE])
        if not (trait := self._target_temperature_trait):
            return None
        if self.hvac_mode == HVACMode.HEAT:
            return trait.heat_celsius
        if self.hvac_mode == HVACMode.COOL:
            return trait.cool_celsius
        return None

    @property
    @override
    def target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature."""
        temperature = self._pending_temperature
        if temperature and ATTR_TARGET_TEMP_HIGH in temperature.kwargs:
            return cast(float, temperature.kwargs[ATTR_TARGET_TEMP_HIGH])
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        if not (trait := self._target_temperature_trait):
            return None
        return trait.cool_celsius

    @property
    @override
    def target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature."""
        temperature = self._pending_temperature
        if temperature and ATTR_TARGET_TEMP_LOW in temperature.kwargs:
            return cast(float, temperature.kwargs[ATTR_TARGET_TEMP_LOW])
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        if not (trait := self._target_temperature_trait):
            return None
        return trait.heat_celsius

    @property
    def _target_temperature_trait(
        self,
    ) -> ThermostatEcoTrait | ThermostatTemperatureSetpointTrait | None:
        """Return the correct trait with a target temp depending on mode."""
        if (
            self.preset_mode == PRESET_ECO
            and ThermostatEcoTrait.NAME in self._device.traits
        ):
            return cast(
                ThermostatEcoTrait, self._device.traits[ThermostatEcoTrait.NAME]
            )
        if ThermostatTemperatureSetpointTrait.NAME in self._device.traits:
            return cast(
                ThermostatTemperatureSetpointTrait,
                self._device.traits[ThermostatTemperatureSetpointTrait.NAME],
            )
        return None

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the current operation (e.g. heat, cool, idle)."""
        hvac_mode = HVACMode.OFF
        if ThermostatModeTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatModeTrait.NAME]
            if trait.mode in THERMOSTAT_MODE_MAP:
                hvac_mode = THERMOSTAT_MODE_MAP[trait.mode]
        return hvac_mode

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action (heating, cooling)."""
        trait = self._device.traits[ThermostatHvacTrait.NAME]
        if trait.status == "OFF" and self.hvac_mode != HVACMode.OFF:
            return HVACAction.IDLE
        return THERMOSTAT_HVAC_STATUS_MAP.get(trait.status)

    @property
    @override
    def preset_mode(self) -> str:
        """Return the current active preset."""
        if ThermostatEcoTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatEcoTrait.NAME]
            return PRESET_MODE_MAP.get(trait.mode, PRESET_NONE)
        return PRESET_NONE

    @property
    @override
    def preset_modes(self) -> list[str]:
        """Return the available presets."""
        if ThermostatEcoTrait.NAME not in self._device.traits:
            return []
        return [
            PRESET_MODE_MAP[mode]
            for mode in self._device.traits[ThermostatEcoTrait.NAME].available_modes
            if mode in PRESET_MODE_MAP
        ]

    @property
    @override
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        if (
            self.supported_features & ClimateEntityFeature.FAN_MODE
            and FanTrait.NAME in self._device.traits
        ):
            trait = self._device.traits[FanTrait.NAME]
            return FAN_MODE_MAP.get(trait.timer_mode, FAN_OFF)
        return FAN_OFF

    @property
    @override
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        if (
            self.supported_features & ClimateEntityFeature.FAN_MODE
            and FanTrait.NAME in self._device.traits
        ):
            return FAN_INV_MODES
        return []

    def _get_supported_features(self) -> ClimateEntityFeature:
        """Compute the bitmap of supported features from the current state."""
        features = ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        if HVACMode.HEAT_COOL in self.hvac_modes:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if HVACMode.HEAT in self.hvac_modes or HVACMode.COOL in self.hvac_modes:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if ThermostatEcoTrait.NAME in self._device.traits:
            features |= ClimateEntityFeature.PRESET_MODE
        if FanTrait.NAME in self._device.traits:
            # Fan trait may be present without actually support fan mode
            fan_trait = self._device.traits[FanTrait.NAME]
            if fan_trait.timer_mode is not None:
                features |= ClimateEntityFeature.FAN_MODE
        return features

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        api_mode = THERMOSTAT_INV_MODE_MAP[hvac_mode]
        trait = self._device.traits[ThermostatModeTrait.NAME]
        async with self._command_lock:
            if (pending := self._pending_temperature) and not pending.sent:
                await self._async_send_pending_temperature(pending)
            try:
                await trait.set_mode(api_mode)
            except ApiException as err:
                raise HomeAssistantError(
                    f"Error setting {self.entity_id} HVAC mode to {hvac_mode}: {err}"
                ) from err

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Schedule a new target temperature after a trailing-edge debounce."""
        hvac_mode = (
            temperature.hvac_mode
            if (temperature := self._pending_temperature)
            else self.hvac_mode
        )
        if (new_hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            hvac_mode = new_hvac_mode
            await self.async_set_hvac_mode(hvac_mode)
        if ThermostatTemperatureSetpointTrait.NAME not in self._device.traits:
            raise HomeAssistantError(
                f"Error setting {self.entity_id} temperature to {kwargs}: "
                "Unable to find setpoint trait."
            )

        # Normalize narrow ranges before optimistic state hides the previous target.
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if low_temp and high_temp and high_temp - low_temp < MIN_TEMP_RANGE:
            current_high = self.target_temperature_high
            if current_high and abs(high_temp - current_high) < 0.01:
                high_temp = low_temp + MIN_TEMP_RANGE
            else:
                low_temp = high_temp - MIN_TEMP_RANGE
            kwargs[ATTR_TARGET_TEMP_LOW] = low_temp
            kwargs[ATTR_TARGET_TEMP_HIGH] = high_temp

        pending = self._pending_temperature = _PendingTemperature(kwargs, hvac_mode)
        self.async_write_ha_state()

        async def async_send_temperature(_now: datetime) -> None:
            async with self._command_lock:
                await self._async_send_pending_temperature(pending)

        async_call_later(
            self.hass, TEMPERATURE_DEBOUNCE_SECONDS, async_send_temperature
        )

    async def _async_send_pending_temperature(
        self, expected: _PendingTemperature
    ) -> None:
        """Send a pending temperature while holding the command lock."""
        # Only let a callback execute the command it scheduled.
        if expected is not self._pending_temperature or expected.sent:
            return

        # Claim before awaiting so a timer and flush cannot both execute the command.
        expected.sent = True
        kwargs = expected.kwargs
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        trait = self._device.traits[ThermostatTemperatureSetpointTrait.NAME]
        succeeded = False
        try:
            if (
                self.preset_mode == PRESET_ECO
                or expected.hvac_mode == HVACMode.HEAT_COOL
            ):
                if low_temp and high_temp:
                    await trait.set_range(low_temp, high_temp)
            elif expected.hvac_mode == HVACMode.COOL and temp:
                await trait.set_cool(temp)
            elif expected.hvac_mode == HVACMode.HEAT and temp:
                await trait.set_heat(temp)
            succeeded = True
        except ApiException:
            _LOGGER.exception(
                "Error setting %s temperature to %s", self.entity_id, kwargs
            )
        finally:
            if self._pending_temperature is expected:
                if succeeded:

                    @callback
                    def clear_pending_temperature(_now: datetime) -> None:
                        if self._pending_temperature is expected:
                            self._pending_temperature = None
                            self.async_write_ha_state()

                    async_call_later(
                        self.hass,
                        TEMPERATURE_PENDING_TIMEOUT_SECONDS,
                        clear_pending_temperature,
                    )
                else:
                    self._pending_temperature = None
                self.async_write_ha_state()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")
        if self.preset_mode == preset_mode:  # API doesn't like duplicate preset modes
            return
        trait = self._device.traits[ThermostatEcoTrait.NAME]
        async with self._command_lock:
            if (pending := self._pending_temperature) and not pending.sent:
                await self._async_send_pending_temperature(pending)
            try:
                await trait.set_mode(PRESET_INV_MODE_MAP[preset_mode])
            except ApiException as err:
                raise HomeAssistantError(
                    f"Error setting {self.entity_id} preset mode to {preset_mode}: {err}"
                ) from err

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan_mode '{fan_mode}'")
        if fan_mode == FAN_ON and self.hvac_mode == HVACMode.OFF:
            raise ValueError(
                "Cannot turn on fan, please set an HVAC mode (e.g. heat/cool) first"
            )
        trait = self._device.traits[FanTrait.NAME]
        duration = None
        if fan_mode != FAN_OFF:
            duration = MAX_FAN_DURATION
        try:
            await trait.set_timer(FAN_INV_MODE_MAP[fan_mode], duration=duration)
        except ApiException as err:
            raise HomeAssistantError(
                f"Error setting {self.entity_id} fan mode to {fan_mode}: {err}"
            ) from err

    async def async_set_fan_timer(self, duration: timedelta) -> None:
        """Set a short term fan timer."""
        if not self.supported_features & ClimateEntityFeature.FAN_MODE:
            raise HomeAssistantError(f"Entity {self.entity_id} does not support fan")

        if self.hvac_mode == HVACMode.OFF:
            raise HomeAssistantError(
                f"Cannot turn on fan for {self.entity_id},"
                " please set an HVAC mode (e.g. heat/cool) first"
            )

        seconds = int(duration.total_seconds())
        if seconds <= 0 or seconds > MAX_FAN_DURATION:
            raise ValueError(
                f"Duration {seconds} for {self.entity_id} must be"
                f" between 1 and {MAX_FAN_DURATION} seconds"
            )

        trait = self._device.traits[FanTrait.NAME]
        try:
            await trait.set_timer(FAN_INV_MODE_MAP[FAN_ON], duration=seconds)
        except ApiException as err:
            raise HomeAssistantError(
                f"Error setting {self.entity_id} fan timer: {err}"
            ) from err
