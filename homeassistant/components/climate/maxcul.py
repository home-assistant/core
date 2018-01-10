"""
Support for MAX! thermostats using the maxcul component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.maxcul/
"""
import logging
import os

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.util.yaml import load_yaml, dump as dump_yaml
from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    PLATFORM_SCHEMA
)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE
)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pymaxcul==0.1.8']

DOMAIN = 'climate.maxcul'

CONF_DEVICE_PATH = 'device_path'
CONF_DEVICE_BAUD_RATE = 'device_baud_rate'
CONF_DEVICE_ID = 'device_id'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICE_PATH): cv.isdevice,
    vol.Required(CONF_DEVICE_BAUD_RATE): cv.positive_int,
    vol.Optional(CONF_DEVICE_ID): cv.positive_int,
})

ATTR_DURATION = 'duration'

YAML_DEVICES = 'maxcul_paired_devices.yaml'

SERIVCE_ENABLE_PAIRING = 'enable_pairing'

SCHEMA_SERVICE_ENABLE_PAIRING = vol.Schema({
    vol.Optional('duration', default=30): cv.positive_int,
})

DESCRIPTION_SERVICE_ENABLE_PAIRING = {
    'description': "Enable pairing for a given duration",
    'fields': {
        ATTR_DURATION: {
            'description': "Duration for which pairing is possible in seconds",
            'example': 30
        }
    }
}

DEFAULT_TEMPERATURE = 12


def _read_paired_devices(path):
    if not os.path.isfile(path):
        return []
    paired_devices = load_yaml(path)
    if not isinstance(paired_devices, list):
        _LOGGER.warning(
            "Paired devices file %s did not contain a list", path)
        return []
    return paired_devices


def _write_paired_devices(path, devices):
    file_descriptor = os.open(path, os.O_WRONLY | os.O_CREAT)
    os.write(file_descriptor, dump_yaml(devices).encode())
    os.close(file_descriptor)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """
    Initialize the maxcul climate platform.

    Reads previously paired devices from a configuration file.
    Starts the thread that communications with the CUL stick.
    Sets up appropriate callback for events from the stick.
    Sets up devices that have previously been paired.
    """
    import maxcul
    path = config[CONF_DEVICE_PATH]
    baud = config[CONF_DEVICE_BAUD_RATE]
    sender_id = config.get(CONF_DEVICE_ID)

    paired_devices_path = hass.config.path(YAML_DEVICES)
    paired_device_ids = _read_paired_devices(paired_devices_path)
    climate_devices = {}
    maxconn = None

    def callback(event, payload):
        """Handle new MAX! events."""
        device_id = payload.get(maxcul.ATTR_DEVICE_ID)
        if device_id is None:
            return
        if event == maxcul.EVENT_THERMOSTAT_UPDATE:
            device = climate_devices.get(device_id)
            if device:
                device.update_from_event(payload)

        elif event in [maxcul.EVENT_DEVICE_PAIRED,
                       maxcul.EVENT_DEVICE_REPAIRED]:
            if device_id in climate_devices:
                return
            device = MaxCulClimate(hass, maxconn, device_id)
            add_devices([device])
            climate_devices[device_id] = device
            _write_paired_devices(
                paired_devices_path,
                climate_devices.keys())

    params = dict(
        device_path=path,
        baudrate=baud,
        paired_devices=list(paired_device_ids),
        callback=callback
    )
    if sender_id:
        params['sender_id'] = sender_id
    maxconn = maxcul.MaxConnection(**params)
    maxconn.start()

    devices = [
        MaxCulClimate(hass, maxconn, device_id)
        for device_id
        in paired_device_ids
    ]
    add_devices(devices)
    for device in devices:
        climate_devices[device.thermostat_id] = device

    def _service_enable_pairing(service):
        duration = service.data.get(ATTR_DURATION)
        maxconn.enable_pairing(duration)

    hass.services.register(
        DOMAIN,
        SERIVCE_ENABLE_PAIRING,
        _service_enable_pairing,
        DESCRIPTION_SERVICE_ENABLE_PAIRING,
        schema=SCHEMA_SERVICE_ENABLE_PAIRING)

    return True


class MaxCulClimate(ClimateDevice):
    """A MAX! thermostat backed by a CUL stick."""

    def __init__(self, hass, maxconn, thermostat_id):
        """Initialize a new device for the given thermostat id."""
        self.entity_id = "climate.maxcul_thermostat_{:x}".format(thermostat_id)
        self._name = "Thermostat {:x}".format(thermostat_id)
        self.thermostat_id = thermostat_id
        self._maxcul_handle = maxconn
        self._current_temperature = None
        self._target_temperature = None
        self._mode = None
        self._battery_low = None

        self._maxcul_handle.wakeup(self.thermostat_id)

    def update_from_event(self, event):
        """Handle thermostat update events."""
        from maxcul import (
            ATTR_DESIRED_TEMPERATURE,
            ATTR_MEASURED_TEMPERATURE, ATTR_MODE,
            ATTR_BATTERY_LOW
        )
        current_temperature = event.get(ATTR_MEASURED_TEMPERATURE)
        target_temperature = event.get(ATTR_DESIRED_TEMPERATURE)
        mode = event.get(ATTR_MODE)
        battery_low = event.get(ATTR_BATTERY_LOW)

        if current_temperature is not None:
            self._current_temperature = current_temperature
        if target_temperature is not None:
            self._target_temperature = target_temperature
        if mode is not None:
            self._mode = mode
        if battery_low is not None:
            self._battery_low = battery_low

        self.async_schedule_update_ha_state()

    @property
    def supported_features(self):
        """Return the features supported by this device."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def should_poll(self):
        """Return whether this device must be polled."""
        return False

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        from maxcul import ATTR_BATTERY_LOW
        return {
            ATTR_BATTERY_LOW: self._battery_low
        }

    @property
    def max_temp(self):
        """Return the maximum temperature for this device."""
        from maxcul import MAX_TEMPERATURE
        return MAX_TEMPERATURE

    @property
    def min_temp(self):
        """Return the minimum temperature for this device."""
        from maxcul import MIN_TEMPERATURE
        return MIN_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the temperature unit of this device."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the currently measured temperature of this device."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature of this device."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return the current operation mode of this device."""
        return self._mode

    @property
    def operation_list(self):
        """All supported operation modes of this device."""
        from maxcul import MODE_AUTO, MODE_MANUAL, MODE_TEMPORARY, MODE_BOOST
        return [MODE_AUTO, MODE_MANUAL, MODE_TEMPORARY, MODE_BOOST]

    def set_temperature(self, **kwargs):
        """Set the target temperature of this device."""
        from maxcul import MODE_MANUAL
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return False

        return self._maxcul_handle.set_temperature(
            self.thermostat_id,
            target_temperature,
            self._mode or MODE_MANUAL)

    def set_operation_mode(self, operation_mode):
        """Set the operation mode of this device."""
        return self._maxcul_handle.set_temperature(
            self.thermostat_id,
            self._target_temperature or DEFAULT_TEMPERATURE,
            operation_mode)
