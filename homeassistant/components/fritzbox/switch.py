"""Support for AVM Fritz!Box smarthome switch devices."""
import logging

import requests

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    ATTR_TEMPERATURE, ENERGY_KILO_WATT_HOUR, TEMP_CELSIUS)

from . import (
    ATTR_STATE_DEVICE_LOCKED, ATTR_STATE_LOCKED, DOMAIN as FRITZBOX_DOMAIN)

DEPENDENCIES = ['fritzbox']

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_CONSUMPTION = 'total_consumption'
ATTR_TOTAL_CONSUMPTION_UNIT = 'total_consumption_unit'
ATTR_TOTAL_CONSUMPTION_UNIT_VALUE = ENERGY_KILO_WATT_HOUR

ATTR_TEMPERATURE_UNIT = 'temperature_unit'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fritzbox smarthome switch platform."""
    devices = []
    fritz_list = hass.data[FRITZBOX_DOMAIN]

    for fritz in fritz_list:
        device_list = fritz.get_devices()
        for device in device_list:
            if device.has_switch:
                devices.append(FritzboxSwitch(device, fritz))

    add_entities(devices)


class FritzboxSwitch(SwitchDevice):
    """The switch class for Fritzbox switches."""

    def __init__(self, device, fritz):
        """Initialize the switch."""
        self._device = device
        self._fritz = fritz

    @property
    def available(self):
        """Return if switch is available."""
        return self._device.present

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._device.switch_state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._device.set_switch_state_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._device.set_switch_state_off()

    def update(self):
        """Get latest data and states from the device."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            _LOGGER.warning("Fritzhome connection error: %s", ex)
            self._fritz.login()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {}
        attrs[ATTR_STATE_DEVICE_LOCKED] = self._device.device_lock
        attrs[ATTR_STATE_LOCKED] = self._device.lock

        if self._device.has_powermeter:
            attrs[ATTR_TOTAL_CONSUMPTION] = "{:.3f}".format(
                (self._device.energy or 0.0) / 1000)
            attrs[ATTR_TOTAL_CONSUMPTION_UNIT] = \
                ATTR_TOTAL_CONSUMPTION_UNIT_VALUE
        if self._device.has_temperature_sensor:
            attrs[ATTR_TEMPERATURE] = \
                str(self.hass.config.units.temperature(
                    self._device.temperature, TEMP_CELSIUS))
            attrs[ATTR_TEMPERATURE_UNIT] = \
                self.hass.config.units.temperature_unit
        return attrs

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.power / 1000
