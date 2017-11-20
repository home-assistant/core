"""
Support for AVM Fritz!Box fritzhome switch devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/switch.fritzhome/
"""
import logging
from homeassistant.components.fritzhome import (
    ATTR_AIN, ATTR_FW_VERSION, ATTR_ID, ATTR_MANUFACTURER, ATTR_PRODUCTNAME,
    DOMAIN)
from homeassistant.components.switch import (SwitchDevice)

DEPENDENCIES = ['fritzhome']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fritzhome switch platform."""
    if DOMAIN not in hass.data:
        return False

    device_list = hass.data[DOMAIN]

    devices = []
    for device in device_list:
        if device.has_switch:
            devices.append(FritzhomeSwitch(hass, device))

    add_devices(devices)


class FritzhomeSwitch(SwitchDevice):
    """The thermostat class for Fritzhome."""

    def __init__(self, hass, device):
        """Initialize the switch."""
        self._device = device
        self._state = None

    @property
    def available(self):
        """Return if switch is available."""
        return self._device.present

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_AIN: self._device.ain,
            ATTR_FW_VERSION: self._device.fw_version,
            ATTR_ID: self._device.id,
            ATTR_MANUFACTURER: self._device.manufacturer,
            ATTR_PRODUCTNAME: self._device.productname,
        }
        return attr

    @property
    def is_on(self):
        """Return true if the switch is on."""
        from pyfritzhome import InvalidError

        try:
            state = self._device.get_switch_state()
        except InvalidError:
            state = None

        return state

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
        except Exception as exc:
            _LOGGER.warning("Updating the state failed: %s", exc)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.power / 1000
