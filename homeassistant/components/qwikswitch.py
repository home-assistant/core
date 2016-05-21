"""
Support for Qwikswitch devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/qwikswitch/
"""
import logging
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.discovery import load_platform

REQUIREMENTS = ['https://github.com/kellerza/pyqwikswitch/archive/v0.1.zip'
                '#pyqwikswitch==0.1']
DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'qwikswitch'
QSUSB = None


class QSToggleEntity(object):
    """Representation of a Qwikswitch Entity.

    Implement base QS methods. Modeled around HA ToggleEntity[1] & should only
    be used in a class that extends both QSToggleEntity *and* ToggleEntity.

    Implemented:
     - QSLight extends QSToggleEntity and Light[2] (ToggleEntity[1])
     - QSSwitch extends QSToggleEntity and SwitchDevice[3] (ToggleEntity[1])

    [1] /helpers/entity.py
    [2] /components/light/__init__.py
    [3] /components/switch/__init__.py
    """

    def __init__(self, qsitem, qsusb):
        """Initialize the ToggleEntity."""
        self._id = qsitem['id']
        self._name = qsitem['name']
        self._qsusb = qsusb
        self._value = qsitem.get('value', 0)
        self._dim = qsitem['type'] == 'dim'

    @property
    def brightness(self):
        """Return the brightness of this light between 0..100."""
        return self._value if self._dim else None

    # pylint: disable=no-self-use
    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Check if device is on (non-zero)."""
        return self._value > 0

    def update_value(self, value):
        """Decode the QSUSB value and update the Home assistant state."""
        if value != self._value:
            self._value = value
            # pylint: disable=no-member
            super().update_ha_state()  # Part of Entity/ToggleEntity
        return self._value

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            self.update_value(kwargs[ATTR_BRIGHTNESS])
        else:
            self.update_value(255)

        return self._qsusb.set(self._id, round(min(self._value, 255)/2.55))

    # pylint: disable=unused-argument
    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.update_value(0)
        return self._qsusb.set(self._id, 0)


def setup(hass, config):
    """Setup the QSUSB component."""
    from pyqwikswitch import QSUsb, CMD_BUTTONS

    # Override which cmd's in /&listen packets will fire events
    # By default only buttons of type [TOGGLE,SCENE EXE,LEVEL]
    cmd_buttons = config[DOMAIN].get('button_events', ','.join(CMD_BUTTONS))
    cmd_buttons = cmd_buttons.split(',')

    try:
        url = config[DOMAIN].get('url', 'http://127.0.0.1:2020')
        dimmer_adjust = float(config[DOMAIN].get('dimmer_adjust', '1'))
        qsusb = QSUsb(url, _LOGGER, dimmer_adjust)

        # Ensure qsusb terminates threads correctly
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             lambda event: qsusb.stop())
    except ValueError as val_err:
        _LOGGER.error(str(val_err))
        return False

    qsusb.ha_devices = qsusb.devices()
    qsusb.ha_objects = {}

    # Identify switches & remove ' Switch' postfix in name
    for item in qsusb.ha_devices:
        if item['type'] == 'rel' and item['name'].lower().endswith(' switch'):
            item['type'] = 'switch'
            item['name'] = item['name'][:-7]

    global QSUSB
    if QSUSB is None:
        QSUSB = {}
    QSUSB[id(qsusb)] = qsusb

    # Load sub-components for qwikswitch
    for comp_name in ('switch', 'light'):
        load_platform(hass, comp_name, 'qwikswitch',
                      {'qsusb_id': id(qsusb)}, config)

    def qs_callback(item):
        """Typically a button press or update signal."""
        # If button pressed, fire a hass event
        if item.get('cmd', '') in cmd_buttons:
            hass.bus.fire('qwikswitch.button.' + item.get('id', '@no_id'))
            return

        # Update all ha_objects
        qsreply = qsusb.devices()
        if qsreply is False:
            return
        for item in qsreply:
            item_id = item.get('id', '')
            if item_id in qsusb.ha_objects:
                qsusb.ha_objects[item_id].update_value(
                    round(min(item['value'], 100) * 2.55))

    qsusb.listen(callback=qs_callback, timeout=30)
    return True
