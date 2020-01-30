"""Support for KNX/IP climate devices."""
from typing import List, Optional

import voluptuous as vol
from xknx.devices import Climate as XknxClimate, ClimateMode as XknxClimateMode
from xknx.knx import HVACOperationMode

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_SLEEP,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

CONF_SETPOINT_SHIFT_ADDRESS = "setpoint_shift_address"
CONF_SETPOINT_SHIFT_STATE_ADDRESS = "setpoint_shift_state_address"
CONF_SETPOINT_SHIFT_STEP = "setpoint_shift_step"
CONF_SETPOINT_SHIFT_MAX = "setpoint_shift_max"
CONF_SETPOINT_SHIFT_MIN = "setpoint_shift_min"
CONF_TEMPERATURE_ADDRESS = "temperature_address"
CONF_TARGET_TEMPERATURE_ADDRESS = "target_temperature_address"
CONF_TARGET_TEMPERATURE_STATE_ADDRESS = "target_temperature_state_address"
CONF_OPERATION_MODE_ADDRESS = "operation_mode_address"
CONF_OPERATION_MODE_STATE_ADDRESS = "operation_mode_state_address"
CONF_CONTROLLER_STATUS_ADDRESS = "controller_status_address"
CONF_CONTROLLER_STATUS_STATE_ADDRESS = "controller_status_state_address"
CONF_CONTROLLER_MODE_ADDRESS = "controller_mode_address"
CONF_CONTROLLER_MODE_STATE_ADDRESS = "controller_mode_state_address"
CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS = "operation_mode_frost_protection_address"
CONF_OPERATION_MODE_NIGHT_ADDRESS = "operation_mode_night_address"
CONF_OPERATION_MODE_COMFORT_ADDRESS = "operation_mode_comfort_address"
CONF_OPERATION_MODES = "operation_modes"
CONF_ON_OFF_ADDRESS = "on_off_address"
CONF_ON_OFF_STATE_ADDRESS = "on_off_state_address"
CONF_ON_OFF_INVERT = "on_off_invert"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"

DEFAULT_NAME = "KNX Climate"
DEFAULT_SETPOINT_SHIFT_STEP = 0.5
DEFAULT_SETPOINT_SHIFT_MAX = 6
DEFAULT_SETPOINT_SHIFT_MIN = -6
DEFAULT_ON_OFF_INVERT = False
# Map KNX operation modes to HA modes. This list might not be full.
OPERATION_MODES = {
    # Map DPT 201.105 HVAC control modes
    "Auto": HVAC_MODE_AUTO,
    "Heat": HVAC_MODE_HEAT,
    "Cool": HVAC_MODE_COOL,
    "Off": HVAC_MODE_OFF,
    "Fan only": HVAC_MODE_FAN_ONLY,
    "Dry": HVAC_MODE_DRY,
}

OPERATION_MODES_INV = dict((reversed(item) for item in OPERATION_MODES.items()))

PRESET_MODES = {
    # Map DPT 201.100 HVAC operating modes to HA presets
    "Frost Protection": PRESET_ECO,
    "Night": PRESET_SLEEP,
    "Standby": PRESET_AWAY,
    "Comfort": PRESET_COMFORT,
}

PRESET_MODES_INV = dict((reversed(item) for item in PRESET_MODES.items()))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_SETPOINT_SHIFT_STEP, default=DEFAULT_SETPOINT_SHIFT_STEP
        ): vol.All(float, vol.Range(min=0, max=2)),
        vol.Optional(
            CONF_SETPOINT_SHIFT_MAX, default=DEFAULT_SETPOINT_SHIFT_MAX
        ): vol.All(int, vol.Range(min=0, max=32)),
        vol.Optional(
            CONF_SETPOINT_SHIFT_MIN, default=DEFAULT_SETPOINT_SHIFT_MIN
        ): vol.All(int, vol.Range(min=-32, max=0)),
        vol.Required(CONF_TEMPERATURE_ADDRESS): cv.string,
        vol.Required(CONF_TARGET_TEMPERATURE_STATE_ADDRESS): cv.string,
        vol.Optional(CONF_TARGET_TEMPERATURE_ADDRESS): cv.string,
        vol.Optional(CONF_SETPOINT_SHIFT_ADDRESS): cv.string,
        vol.Optional(CONF_SETPOINT_SHIFT_STATE_ADDRESS): cv.string,
        vol.Optional(CONF_OPERATION_MODE_ADDRESS): cv.string,
        vol.Optional(CONF_OPERATION_MODE_STATE_ADDRESS): cv.string,
        vol.Optional(CONF_CONTROLLER_STATUS_ADDRESS): cv.string,
        vol.Optional(CONF_CONTROLLER_STATUS_STATE_ADDRESS): cv.string,
        vol.Optional(CONF_CONTROLLER_MODE_ADDRESS): cv.string,
        vol.Optional(CONF_CONTROLLER_MODE_STATE_ADDRESS): cv.string,
        vol.Optional(CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS): cv.string,
        vol.Optional(CONF_OPERATION_MODE_NIGHT_ADDRESS): cv.string,
        vol.Optional(CONF_OPERATION_MODE_COMFORT_ADDRESS): cv.string,
        vol.Optional(CONF_ON_OFF_ADDRESS): cv.string,
        vol.Optional(CONF_ON_OFF_STATE_ADDRESS): cv.string,
        vol.Optional(CONF_ON_OFF_INVERT, default=DEFAULT_ON_OFF_INVERT): cv.boolean,
        vol.Optional(CONF_OPERATION_MODES): vol.All(
            cv.ensure_list, [vol.In(OPERATION_MODES)]
        ),
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up climate(s) for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)
    else:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up climates for KNX platform configured within platform."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXClimate(device))
    async_add_entities(entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up climate for KNX platform configured within platform."""
    climate_mode = XknxClimateMode(
        hass.data[DATA_KNX].xknx,
        name=config[CONF_NAME] + " Mode",
        group_address_operation_mode=config.get(CONF_OPERATION_MODE_ADDRESS),
        group_address_operation_mode_state=config.get(
            CONF_OPERATION_MODE_STATE_ADDRESS
        ),
        group_address_controller_status=config.get(CONF_CONTROLLER_STATUS_ADDRESS),
        group_address_controller_status_state=config.get(
            CONF_CONTROLLER_STATUS_STATE_ADDRESS
        ),
        group_address_controller_mode=config.get(CONF_CONTROLLER_MODE_ADDRESS),
        group_address_controller_mode_state=config.get(
            CONF_CONTROLLER_MODE_STATE_ADDRESS
        ),
        group_address_operation_mode_protection=config.get(
            CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS
        ),
        group_address_operation_mode_night=config.get(
            CONF_OPERATION_MODE_NIGHT_ADDRESS
        ),
        group_address_operation_mode_comfort=config.get(
            CONF_OPERATION_MODE_COMFORT_ADDRESS
        ),
        operation_modes=config.get(CONF_OPERATION_MODES),
    )
    hass.data[DATA_KNX].xknx.devices.add(climate_mode)

    climate = XknxClimate(
        hass.data[DATA_KNX].xknx,
        name=config[CONF_NAME],
        group_address_temperature=config[CONF_TEMPERATURE_ADDRESS],
        group_address_target_temperature=config.get(CONF_TARGET_TEMPERATURE_ADDRESS),
        group_address_target_temperature_state=config[
            CONF_TARGET_TEMPERATURE_STATE_ADDRESS
        ],
        group_address_setpoint_shift=config.get(CONF_SETPOINT_SHIFT_ADDRESS),
        group_address_setpoint_shift_state=config.get(
            CONF_SETPOINT_SHIFT_STATE_ADDRESS
        ),
        setpoint_shift_step=config[CONF_SETPOINT_SHIFT_STEP],
        setpoint_shift_max=config[CONF_SETPOINT_SHIFT_MAX],
        setpoint_shift_min=config[CONF_SETPOINT_SHIFT_MIN],
        group_address_on_off=config.get(CONF_ON_OFF_ADDRESS),
        group_address_on_off_state=config.get(CONF_ON_OFF_STATE_ADDRESS),
        min_temp=config.get(CONF_MIN_TEMP),
        max_temp=config.get(CONF_MAX_TEMP),
        mode=climate_mode,
        on_off_invert=config[CONF_ON_OFF_INVERT],
    )
    hass.data[DATA_KNX].xknx.devices.add(climate)

    async_add_entities([KNXClimate(climate)])


class KNXClimate(ClimateDevice):
    """Representation of a KNX climate device."""

    def __init__(self, device):
        """Initialize of a KNX climate device."""
        self.device = device
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    async def async_added_to_hass(self) -> None:
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()

        self.device.register_device_updated_cb(after_update_callback)
        self.device.mode.register_device_updated_cb(after_update_callback)

    @property
    def name(self) -> str:
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self) -> bool:
        """No polling needed within KNX."""
        return False

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device.temperature.value

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.device.temperature_step

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.device.target_temperature.value

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.device.target_temperature_min

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.device.target_temperature_max

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.device.set_target_temperature(temperature)
        await self.async_update_ha_state()

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        if self.device.supports_on_off and not self.device.is_on:
            return HVAC_MODE_OFF
        if self.device.supports_on_off and self.device.is_on:
            return HVAC_MODE_HEAT
        if self.device.mode.supports_operation_mode:
            return OPERATION_MODES.get(
                self.device.mode.operation_mode.value, HVAC_MODE_HEAT
            )
        return None

    @property
    def hvac_modes(self) -> Optional[List[str]]:
        """Return the list of available operation modes."""
        _operations = [
            OPERATION_MODES.get(operation_mode.value)
            for operation_mode in self.device.mode.operation_modes
        ]

        if self.device.supports_on_off:
            _operations.append(HVAC_MODE_HEAT)
            _operations.append(HVAC_MODE_OFF)

        return [op for op in _operations if op is not None]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set operation mode."""
        if self.device.supports_on_off and hvac_mode == HVAC_MODE_OFF:
            await self.device.turn_off()
        elif self.device.supports_on_off and hvac_mode == HVAC_MODE_HEAT:
            await self.device.turn_on()
        elif self.device.mode.supports_operation_mode:
            knx_operation_mode = HVACOperationMode(OPERATION_MODES_INV.get(hvac_mode))
            await self.device.mode.set_operation_mode(knx_operation_mode)
            await self.async_update_ha_state()

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self.device.mode.supports_operation_mode:
            return PRESET_MODES.get(self.device.mode.operation_mode.value, PRESET_AWAY)
        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        _presets = [
            PRESET_MODES.get(operation_mode.value)
            for operation_mode in self.device.mode.operation_modes
        ]

        return list(filter(None, _presets))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.device.mode.supports_operation_mode:
            knx_operation_mode = HVACOperationMode(PRESET_MODES_INV.get(preset_mode))
            await self.device.mode.set_operation_mode(knx_operation_mode)
            await self.async_update_ha_state()
