"""
Support for Qwikswitch lights and switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/qwikswitch
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
    """Representation of a Qwikswitch Entiry.

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
        """Initialize the light."""
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
        # pylint: disable=no-member
        super().update_ha_state()  # Part of Entity/ToggleEntity
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


# pylint: disable=too-many-locals
def setup(hass, config):
    """Setup the QSUSB component."""
    from pyqwikswitch import QSUsb

    try:
        url = config[DOMAIN].get('url', 'http://127.0.0.1:2020')
        qsusb = QSUsb(url, _LOGGER)

        # Ensure qsusb terminates threads correctly
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             lambda event: qsusb.stop())
    except ValueError as val_err:
        _LOGGER.error(str(val_err))
        return False

    qsusb.ha_devices = qsusb.devices()
    qsusb.ha_objects = {}

    global QSUSB
    if QSUSB is None:
        QSUSB = {}
    QSUSB[id(qsusb)] = qsusb

    # Register add_device callbacks onto the gloabl ADD_DEVICES
    # Switch called first since they are [type=rel] and end with ' switch'
    for comp_name in ('switch', 'light'):
        load_platform(hass, comp_name, 'qwikswitch',
                      {'qsusb_id': id(qsusb)}, config)

    def qs_callback(item):
        """Typically a btn press or update signal."""
        from pyqwikswitch import CMD_BUTTONS

        # If button pressed, fire a hass event
        if item.get('type', '') in CMD_BUTTONS:
            _LOGGER.info('qwikswitch.button.%s', item['id'])
            hass.bus.fire('qwikswitch.button.{}'.format(item['id']))
            return

        # Update all ha_objects
        qsreply = qsusb.devices()
        if qsreply is False:
            return
        for item in qsreply:
            item_id = item.get('id', '')
            if item_id in qsusb.ha_objects:
                qsusb.ha_objects[item_id].update_value(item['value'])

    qsusb.listen(callback=qs_callback, timeout=10)
    return True
