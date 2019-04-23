"""Support for KNX/IP climate devices."""
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    STATE_DRY, STATE_ECO, STATE_FAN_ONLY, STATE_HEAT, STATE_IDLE, STATE_MANUAL,
    SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

CONF_SETPOINT_SHIFT_ADDRESS = 'setpoint_shift_address'
CONF_SETPOINT_SHIFT_STATE_ADDRESS = 'setpoint_shift_state_address'
CONF_SETPOINT_SHIFT_STEP = 'setpoint_shift_step'
CONF_SETPOINT_SHIFT_MAX = 'setpoint_shift_max'
CONF_SETPOINT_SHIFT_MIN = 'setpoint_shift_min'
CONF_TEMPERATURE_ADDRESS = 'temperature_address'
CONF_TARGET_TEMPERATURE_ADDRESS = 'target_temperature_address'
CONF_TARGET_TEMPERATURE_STATE_ADDRESS = 'target_temperature_state_address'
CONF_OPERATION_MODE_ADDRESS = 'operation_mode_address'
CONF_OPERATION_MODE_STATE_ADDRESS = 'operation_mode_state_address'
CONF_CONTROLLER_STATUS_ADDRESS = 'controller_status_address'
CONF_CONTROLLER_STATUS_STATE_ADDRESS = 'controller_status_state_address'
CONF_CONTROLLER_MODE_ADDRESS = 'controller_mode_address'
CONF_CONTROLLER_MODE_STATE_ADDRESS = 'controller_mode_state_address'
CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS = \
    'operation_mode_frost_protection_address'
CONF_OPERATION_MODE_NIGHT_ADDRESS = 'operation_mode_night_address'
CONF_OPERATION_MODE_COMFORT_ADDRESS = 'operation_mode_comfort_address'
CONF_OPERATION_MODES = 'operation_modes'
CONF_ON_OFF_ADDRESS = 'on_off_address'
CONF_ON_OFF_STATE_ADDRESS = 'on_off_state_address'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'

DEFAULT_NAME = 'KNX Climate'
DEFAULT_SETPOINT_SHIFT_STEP = 0.5
DEFAULT_SETPOINT_SHIFT_MAX = 6
DEFAULT_SETPOINT_SHIFT_MIN = -6
# Map KNX operation modes to HA modes. This list might not be full.
OPERATION_MODES = {
    # Map DPT 201.100 HVAC operating modes
    "Frost Protection": STATE_MANUAL,
    "Night": STATE_IDLE,
    "Standby": STATE_ECO,
    "Comfort": STATE_HEAT,
    # Map DPT 201.104 HVAC control modes
    "Fan only": STATE_FAN_ONLY,
    "Dehumidification": STATE_DRY
}

OPERATION_MODES_INV = dict((
    reversed(item) for item in OPERATION_MODES.items()))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_TEMPERATURE_ADDRESS): cv.string,
    vol.Required(CONF_TARGET_TEMPERATURE_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_TARGET_TEMPERATURE_ADDRESS): cv.string,
    vol.Optional(CONF_SETPOINT_SHIFT_ADDRESS): cv.string,
    vol.Optional(CONF_SETPOINT_SHIFT_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_SETPOINT_SHIFT_STEP,
                 default=DEFAULT_SETPOINT_SHIFT_STEP): vol.All(
                     float, vol.Range(min=0, max=2)),
    vol.Optional(CONF_SETPOINT_SHIFT_MAX, default=DEFAULT_SETPOINT_SHIFT_MAX):
        vol.All(int, vol.Range(min=0, max=32)),
    vol.Optional(CONF_SETPOINT_SHIFT_MIN, default=DEFAULT_SETPOINT_SHIFT_MIN):
        vol.All(int, vol.Range(min=-32, max=0)),
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
    vol.Optional(CONF_OPERATION_MODES):
        vol.All(cv.ensure_list, [vol.In(OPERATION_MODES)]),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
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
    import xknx

    climate_mode = xknx.devices.ClimateMode(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME) + " Mode",
        group_address_operation_mode=config.get(CONF_OPERATION_MODE_ADDRESS),
        group_address_operation_mode_state=config.get(
            CONF_OPERATION_MODE_STATE_ADDRESS),
        group_address_controller_status=config.get(
            CONF_CONTROLLER_STATUS_ADDRESS),
        group_address_controller_status_state=config.get(
            CONF_CONTROLLER_STATUS_STATE_ADDRESS),
        group_address_controller_mode=config.get(
            CONF_CONTROLLER_MODE_ADDRESS),
        group_address_controller_mode_state=config.get(
            CONF_CONTROLLER_MODE_STATE_ADDRESS),
        group_address_operation_mode_protection=config.get(
            CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS),
        group_address_operation_mode_night=config.get(
            CONF_OPERATION_MODE_NIGHT_ADDRESS),
        group_address_operation_mode_comfort=config.get(
            CONF_OPERATION_MODE_COMFORT_ADDRESS),
        operation_modes=config.get(
            CONF_OPERATION_MODES))
    hass.data[DATA_KNX].xknx.devices.add(climate_mode)

    climate = xknx.devices.Climate(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address_temperature=config[CONF_TEMPERATURE_ADDRESS],
        group_address_target_temperature=config.get(
            CONF_TARGET_TEMPERATURE_ADDRESS),
        group_address_target_temperature_state=config[
            CONF_TARGET_TEMPERATURE_STATE_ADDRESS],
        group_address_setpoint_shift=config.get(CONF_SETPOINT_SHIFT_ADDRESS),
        group_address_setpoint_shift_state=config.get(
            CONF_SETPOINT_SHIFT_STATE_ADDRESS),
        setpoint_shift_step=config.get(CONF_SETPOINT_SHIFT_STEP),
        setpoint_shift_max=config.get(CONF_SETPOINT_SHIFT_MAX),
        setpoint_shift_min=config.get(CONF_SETPOINT_SHIFT_MIN),
        group_address_on_off=config.get(CONF_ON_OFF_ADDRESS),
        group_address_on_off_state=config.get(CONF_ON_OFF_STATE_ADDRESS),
        min_temp=config.get(CONF_MIN_TEMP),
        max_temp=config.get(CONF_MAX_TEMP),
        mode=climate_mode)
    hass.data[DATA_KNX].xknx.devices.add(climate)

    async_add_entities([KNXClimate(climate)])


class KNXClimate(ClimateDevice):
    """Representation of a KNX climate device."""

    def __init__(self, device):
        """Initialize of a KNX climate device."""
        self.device = device
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = SUPPORT_TARGET_TEMPERATURE
        if self.device.mode.supports_operation_mode:
            support |= SUPPORT_OPERATION_MODE
        if self.device.supports_on_off:
            support |= SUPPORT_ON_OFF
        return support

    async def async_added_to_hass(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
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
        return self.device.setpoint_shift_step

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

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.device.set_target_temperature(temperature)
        await self.async_update_ha_state()

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self.device.mode.supports_operation_mode:
            return OPERATION_MODES.get(self.device.mode.operation_mode.value)
        return None

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [OPERATION_MODES.get(operation_mode.value) for
                operation_mode in
                self.device.mode.operation_modes]

    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if self.device.mode.supports_operation_mode:
            from xknx.knx import HVACOperationMode
            knx_operation_mode = HVACOperationMode(
                OPERATION_MODES_INV.get(operation_mode))
            await self.device.mode.set_operation_mode(knx_operation_mode)
            await self.async_update_ha_state()

    @property
    def is_on(self):
        """Return true if the device is on."""
        if self.device.supports_on_off:
            return self.device.is_on
        return None

    async def async_turn_on(self):
        """Turn on."""
        await self.device.turn_on()

    async def async_turn_off(self):
        """Turn off."""
        await self.device.turn_off()
