"""Support for interface with a Gree climate systems."""
from datetime import timedelta
import logging
from typing import List

from greeclimate.exceptions import DeviceTimeoutError

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import (
    DOMAIN,
    FAN_MEDIUM_HIGH,
    FAN_MEDIUM_LOW,
    MAX_ERRORS,
    MAX_TEMP,
    MIN_TEMP,
    TARGET_TEMPERATURE_STEP,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)
PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Gree HVAC device from a config entry."""
    async_add_entities(
        GreeSwitchEntity(device) for device in hass.data[DOMAIN].pop("pending")
    )


class GreeSwitchEntity(SwitchEntity):
    """Representation of a Gree HVAC device."""

    def __init__(self, device):
        """Initialize the Gree device."""
        self._device = device
        self._name = device.device_info.name
        self._mac = device.device_info.mac
        self._available = False
        self._error_count = 0

    # Investigate https://developers.home-assistant.io/docs/integration_fetching_data/#coordinated-single-api-poll-for-data-for-all-entities
    async def async_update(self):
        """Update the state of the device."""
        try:
            await self._device.update_state()

            if not self._available and self._error_count:
                _LOGGER.warning(
                    "Device is available: %s (%s)",
                    self._name,
                    str(self._device.device_info),
                )

            self._available = True
            self._error_count = 0
        except DeviceTimeoutError:
            self._error_count += 1

            # Under normal conditions GREE units timeout every once in a while
            if self._available and self._error_count >= MAX_ERRORS:
                self._available = False
                _LOGGER.warning(
                    "Device is unavailable: %s (%s)",
                    self._name,
                    self._device.device_info,
                )
        except Exception:  # pylint: disable=broad-except
            # Under normal conditions GREE units timeout every once in a while
            if self._available:
                self._available = False
                _LOGGER.exception(
                    "Unknown exception caught during update by gree device: %s (%s)",
                    self._name,
                    self._device.device_info,
                )

    async def _push_state_update(self):
        """Send state updates to the physical device."""
        try:
            return await self._device.push_state_update()
        except DeviceTimeoutError:
            self._error_count += 1

            # Under normal conditions GREE units timeout every once in a while
            if self._available and self._error_count >= MAX_ERRORS:
                self._available = False
                _LOGGER.warning(
                    "Device timedout while sending state update: %s (%s)",
                    self._name,
                    self._device.device_info,
                )
        except Exception:  # pylint: disable=broad-except
            # Under normal conditions GREE units timeout every once in a while
            if self._available:
                self._available = False
                _LOGGER.exception(
                    "Unknown exception caught while sending state update to: %s (%s)",
                    self._name,
                    self._device.device_info,
                )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique id for the device."""
        return self._mac

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._mac)},
            "manufacturer": "Gree",
            "connections": {(CONNECTION_NETWORK_MAC, self._mac)},
        }

    @property
    def temperature_unit(self) -> str:
        """Return the temperature units for the device."""
        units = self._device.temperature_units
        return TEMP_CELSIUS if units == TemperatureUnits.C else TEMP_FAHRENHEIT

    @property
    def precision(self) -> float:
        """Return the precision of temperature for the device."""
        return PRECISION_WHOLE

    @property
    def current_temperature(self) -> float:
        """Return the target temperature, gree devices don't provide internal temp."""
        return self.target_temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature for the device."""
        return self._device.target_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise ValueError(f"Missing parameter {ATTR_TEMPERATURE}")

        temperature = kwargs[ATTR_TEMPERATURE]
        _LOGGER.debug(
            "Setting temperature to %d for %s",
            temperature,
            self._name,
        )

        self._device.target_temperature = round(temperature)
        await self._push_state_update()

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature supported by the device."""
        return MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature supported by the device."""
        return MAX_TEMP

    @property
    def target_temperature_step(self) -> float:
        """Return the target temperature step support by the device."""
        return TARGET_TEMPERATURE_STEP

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode for the device."""
        if not self._device.power:
            return HVAC_MODE_OFF

        return HVAC_MODES.get(self._device.mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            raise ValueError(f"Invalid hvac_mode: {hvac_mode}")

        _LOGGER.debug(
            "Setting HVAC mode to %s for device %s",
            hvac_mode,
            self._name,
        )

        if hvac_mode == HVAC_MODE_OFF:
            self._device.power = False
            await self._push_state_update()
            return

        if not self._device.power:
            self._device.power = True

        self._device.mode = HVAC_MODES_REVERSE.get(hvac_mode)
        await self._push_state_update()

    @property
    def hvac_modes(self) -> List[str]:
        """Return the HVAC modes support by the device."""
        modes = [*HVAC_MODES_REVERSE]
        modes.append(HVAC_MODE_OFF)
        return modes

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode for the device."""
        if self._device.steady_heat:
            return PRESET_AWAY
        if self._device.power_save:
            return PRESET_ECO
        if self._device.sleep:
            return PRESET_SLEEP
        if self._device.turbo:
            return PRESET_BOOST
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"Invalid preset mode: {preset_mode}")

        _LOGGER.debug(
            "Setting preset mode to %s for device %s",
            preset_mode,
            self._name,
        )

        self._device.steady_heat = False
        self._device.power_save = False
        self._device.turbo = False
        self._device.sleep = False

        if preset_mode == PRESET_AWAY:
            self._device.steady_heat = True
        elif preset_mode == PRESET_ECO:
            self._device.power_save = True
        elif preset_mode == PRESET_BOOST:
            self._device.turbo = True
        elif preset_mode == PRESET_SLEEP:
            self._device.sleep = True

        await self._push_state_update()

    @property
    def preset_modes(self) -> List[str]:
        """Return the preset modes support by the device."""
        return PRESET_MODES

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode for the device."""
        speed = self._device.fan_speed
        return FAN_MODES.get(speed)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode not in FAN_MODES_REVERSE:
            raise ValueError(f"Invalid fan mode: {fan_mode}")

        self._device.fan_speed = FAN_MODES_REVERSE.get(fan_mode)
        await self._push_state_update()

    @property
    def fan_modes(self) -> List[str]:
        """Return the fan modes support by the device."""
        return [*FAN_MODES_REVERSE]

    @property
    def swing_mode(self) -> str:
        """Return the current swing mode for the device."""
        h_swing = self._device.horizontal_swing == HorizontalSwing.FullSwing
        v_swing = self._device.vertical_swing == VerticalSwing.FullSwing

        if h_swing and v_swing:
            return SWING_BOTH
        if h_swing:
            return SWING_HORIZONTAL
        if v_swing:
            return SWING_VERTICAL
        return SWING_OFF

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        if swing_mode not in SWING_MODES:
            raise ValueError(f"Invalid swing mode: {swing_mode}")

        _LOGGER.debug(
            "Setting swing mode to %s for device %s",
            swing_mode,
            self._name,
        )

        self._device.horizontal_swing = HorizontalSwing.Center
        self._device.vertical_swing = VerticalSwing.FixedMiddle
        if swing_mode in (SWING_BOTH, SWING_HORIZONTAL):
            self._device.horizontal_swing = HorizontalSwing.FullSwing
        if swing_mode in (SWING_BOTH, SWING_VERTICAL):
            self._device.vertical_swing = VerticalSwing.FullSwing

        await self._push_state_update()

    @property
    def swing_modes(self) -> List[str]:
        """Return the swing modes currently supported for this device."""
        return SWING_MODES

    @property
    def supported_features(self) -> int:
        """Return the supported features for this device integration."""
        return SUPPORTED_FEATURES
