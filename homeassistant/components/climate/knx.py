"""
Support for KNX/IP climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.knx/
"""
import asyncio
import voluptuous as vol

from homeassistant.components.knx import DATA_KNX, ATTR_DISCOVER_DEVICES
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.const import CONF_NAME, TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_SETPOINT_ADDRESS = 'setpoint_address'
CONF_TEMPERATURE_ADDRESS = 'temperature_address'
CONF_TARGET_TEMPERATURE_ADDRESS = 'target_temperature_address'
CONF_OPERATION_MODE_ADDRESS = 'operation_mode_address'
CONF_OPERATION_MODE_STATE_ADDRESS = 'operation_mode_state_address'
CONF_CONTROLLER_STATUS_ADDRESS = 'controller_status_address'
CONF_CONTROLLER_STATUS_STATE_ADDRESS = 'controller_status_state_address'
CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS = \
    'operation_mode_frost_protection_address'
CONF_OPERATION_MODE_NIGHT_ADDRESS = 'operation_mode_night_address'
CONF_OPERATION_MODE_COMFORT_ADDRESS = 'operation_mode_comfort_address'

DEFAULT_NAME = 'KNX Climate'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_SETPOINT_ADDRESS): cv.string,
    vol.Required(CONF_TEMPERATURE_ADDRESS): cv.string,
    vol.Required(CONF_TARGET_TEMPERATURE_ADDRESS): cv.string,
    vol.Optional(CONF_OPERATION_MODE_ADDRESS): cv.string,
    vol.Optional(CONF_OPERATION_MODE_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_CONTROLLER_STATUS_ADDRESS): cv.string,
    vol.Optional(CONF_CONTROLLER_STATUS_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS): cv.string,
    vol.Optional(CONF_OPERATION_MODE_NIGHT_ADDRESS): cv.string,
    vol.Optional(CONF_OPERATION_MODE_COMFORT_ADDRESS): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Set up climate(s) for KNX platform."""
    if DATA_KNX not in hass.data \
            or not hass.data[DATA_KNX].initialized:
        return False

    if discovery_info is not None:
        async_add_devices_discovery(hass, discovery_info, async_add_devices)
    else:
        async_add_devices_config(hass, config, async_add_devices)

    return True


@callback
def async_add_devices_discovery(hass, discovery_info, async_add_devices):
    """Set up climates for KNX platform configured within plattform."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXClimate(hass, device))
    async_add_devices(entities)


@callback
def async_add_devices_config(hass, config, async_add_devices):
    """Set up climate for KNX platform configured within plattform."""
    import xknx
    climate = xknx.devices.Climate(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address_temperature=config.get(
            CONF_TEMPERATURE_ADDRESS),
        group_address_target_temperature=config.get(
            CONF_TARGET_TEMPERATURE_ADDRESS),
        group_address_setpoint=config.get(
            CONF_SETPOINT_ADDRESS),
        group_address_operation_mode=config.get(
            CONF_OPERATION_MODE_ADDRESS),
        group_address_operation_mode_state=config.get(
            CONF_OPERATION_MODE_STATE_ADDRESS),
        group_address_controller_status=config.get(
            CONF_CONTROLLER_STATUS_ADDRESS),
        group_address_controller_status_state=config.get(
            CONF_CONTROLLER_STATUS_STATE_ADDRESS),
        group_address_operation_mode_protection=config.get(
            CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS),
        group_address_operation_mode_night=config.get(
            CONF_OPERATION_MODE_NIGHT_ADDRESS),
        group_address_operation_mode_comfort=config.get(
            CONF_OPERATION_MODE_COMFORT_ADDRESS))
    hass.data[DATA_KNX].xknx.devices.add(climate)
    async_add_devices([KNXClimate(hass, climate)])


class KNXClimate(ClimateDevice):
    """Representation of a KNX climate."""

    def __init__(self, hass, device):
        """Initialization of KNXClimate."""
        self.device = device
        self.hass = hass
        self.async_register_callbacks()

        self._unit_of_measurement = TEMP_CELSIUS
        self._away = False  # not yet supported
        self._is_fan_on = False  # not yet supported

    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        @asyncio.coroutine
        def after_update_callback(device):
            """Callback after device was updated."""
            # pylint: disable=unused-argument
            yield from self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

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
        return self.device.temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.device.supports_target_temperature:
            return self.device.target_temperature
        return None

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self.device.supports_target_temperature:
            yield from self.device.set_target_temperature(temperature)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self.device.supports_operation_mode:
            return self.device.operation_mode.value
        return None

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [operation_mode.value for
                operation_mode in
                self.device.get_supported_operation_modes()]

    @asyncio.coroutine
    def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if self.device.supports_operation_mode:
            from xknx.knx import HVACOperationMode
            knx_operation_mode = HVACOperationMode(operation_mode)
            yield from self.device.set_operation_mode(knx_operation_mode)
