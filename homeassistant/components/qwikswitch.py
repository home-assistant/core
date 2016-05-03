# pylint: disable=line-too-long
"""
Support for Qwikswitch lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/qwikswitch

* QSToggleEntity implement base QS methods(modeled around HA ToggleEntity)
* QSLight extends QSToggleEntity and Light(ToggleEntity)
* QSSwitch extends QSToggleEntity and SwitchDevice(ToggleEntity)

[ToggleEntity](https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/helpers/entity.py)
[Light](https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/light/__init__.py)
[SwitchDevice](https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/switch/__init__.py)
"""
# pylint: enable=line-too-long

import logging
# import requests
# import math
# import threading
# from time import sleep
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.light import (
    Light,
    ATTR_BRIGHTNESS
)
from homeassistant.components.switch import SwitchDevice
from homeassistant.components.discovery import discover

# from homeassistant import bootstrap
# from homeassistant.const import (
#    ATTR_DISCOVERED, ATTR_SERVICE, EVENT_PLATFORM_DISCOVERED)
# from homeassistant.loader import get_component
# from homeassistant.helpers import validate_config

import pyqwikswitch


REQUIREMENTS = ['requests',
                'https://github.com/kellerza/pyqwikswitch/archive/v0.1.zip'
                '#pyqwikswitch==0.1']
DEPENDENCIES = ['switch']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'qwikswitch'
DISCOVER_LIGHTS = 'qwikswitch.light'
DISCOVER_SWITCHES = 'qwikswitch.switch'

QSUSB = None


def setup(hass, config):
    """Setup the QSUSB component."""
    url = config[DOMAIN].get('url', 'http://127.0.0.1:2020')

    try:
        global QSUSB  # pylint: disable=global-statement
        QSUSB = QSUsbManager(hass, url, _LOGGER)
    except ValueError as val_err:
        _LOGGER.error(str(val_err))
        return False

    # Register add_device callbacks onto the gloabl QSUSB
    for comp_name in ('switch', 'light'):
        discover(hass, 'qwikswitch.'+comp_name, component=comp_name)
        # discover seems to wrap these commands -- simplify
        # component = get_component(comp_name)
        # bootstrap.setup_component(hass, component.DOMAIN, config)
        # hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
        #              {ATTR_SERVICE: '{}.qwikswitch'.format(comp_name),
        #               ATTR_DISCOVERED: {}})

    QSUSB.listen(timeout=10)

    return True


class QSUsbManager(pyqwikswitch.QSUsb):
    """QS USB listener."""

    def __init__(self, hass, url, logger):
        """Setup QSUsb devices."""
        super().__init__(url, logger)
        self.hass = hass
        self.qsdevices = {'': None}

        # pylint: disable=unused-argument
        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                  lambda event: self.stop())

    @staticmethod
    def add_devices_light(devices):
        """Dummy method until discovery adds correct one."""
        _LOGGER.error('add_devices_light not assigned by discovered platforms')

    @staticmethod
    def add_devices_switch(devices):
        """Dummy method until discovery adds correct one."""
        _LOGGER.error('add_devices_light not assigned by discovered platforms')

    def callback(self, item):
        """Typically a btn press or update signal."""
        if item.get('type', '') in pyqwikswitch.CMD_BUTTONS:
            # Button press, fire a hass event
            _LOGGER.info('qwikswitch.button.%s', item['id'])
            QSUSB.hass.bus.fire('qwikswitch.button.{}'.format(item['id']))
            return

        # Perform a normal update of all devices
        qsreply = self.devices()
        if qsreply is False:
            return
        for item in qsreply:
            item_id = item.get('id', '')

            # Add this device if it is not known
            if item_id not in self.qsdevices:
                _LOGGER.info('Add QS device %s', item['name'])
                if item['type'] == 'dim':
                    self.add_devices_light([QSLight(item, self)])
                elif item['type'] == 'rel':
                    if item['name'].lower().endswith(' switch'):
                        # Remove the ' Switch' name postfix for HA
                        item['name'] = item['name'][:-7]
                        self.add_devices_switch([QSSwitch(item, self)])
                    else:
                        self.add_devices_light([QSLight(item, self)])
                else:
                    self.qsdevices[item_id] = None
                    _LOGGER.error('QwikSwitch: type=%s not supported',
                                  item['type'])

            if self.qsdevices.get(item_id, '') is not None:
                self.qsdevices[item_id].update_value(item['value'])


class QSToggleEntity(object):
    """Representation of a Qwikswitch Entiry."""

    def __init__(self, qsitem, qsusb):
        """Initialize the light."""
        self._id = qsitem['id']
        self._name = qsitem['name']
        self._qsusb = qsusb
        self._qsusb.qsdevices[qsitem['id']] = self
        self._value = qsitem.get('value', 0)
        self._dim = qsitem['type'] == 'dim'

    @property
    def brightness(self):
        """Return the brightness of this light between 0..100."""
        return self._value if self._dim else None

    # pylint: disable=no-self-use
    @property
    def should_poll(self):
        """State Polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Check if On (non-zero)."""
        return self._value > 0

    def update_value(self, value):
        """Decode QSUSB value & update HA state."""
        self._value = value
        if self.hass is not None:
            self.update_ha_state()
        return self._value

    # pylint: disable=unused-argument
    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._value = kwargs[ATTR_BRIGHTNESS]
        else:
            self._value = 100
        return self._qsusb.set(self._id, self._value)

    # pylint: disable=unused-argument
    def turn_off(self, **kwargs):
        """Turn the device off."""
        return self._qsusb.set(self._id, 0)


class QSLight(QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""
