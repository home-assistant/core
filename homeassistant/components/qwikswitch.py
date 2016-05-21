"""
Support for Qwikswitch devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/qwikswitch/
"""
import logging
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.discovery import load_platform

REQUIREMENTS = ['https://github.com/kellerza/pyqwikswitch/archive/v0.3.zip'
                '#pyqwikswitch==0.3']
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
        from pyqwikswitch import (QS_ID, QS_NAME, QSType, PQS_VALUE, PQS_TYPE)
        self._id = qsitem[QS_ID]
        self._name = qsitem[QS_NAME]
        self._value = qsitem[PQS_VALUE]
        self._qsusb = qsusb
        self._dim = qsitem[PQS_TYPE] == QSType.dimmer

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
        newvalue = 255
        if ATTR_BRIGHTNESS in kwargs:
            newvalue = kwargs[ATTR_BRIGHTNESS]
        if self._qsusb.set(self._id, round(min(newvalue, 255)/2.55)) >= 0:
            self.update_value(newvalue)

    # pylint: disable=unused-argument
    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._qsusb.set(self._id, 0) >= 0:
            self.update_value(0)


# pylint: disable=too-many-locals
def setup(hass, config):
    """Setup the QSUSB component."""
    from pyqwikswitch import (QSUsb, CMD_BUTTONS, QS_NAME, QS_ID, QS_CMD,
                              QS_TYPE, PQS_VALUE, PQS_TYPE, QSType)

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
        if item[PQS_TYPE] == QSType.relay and \
           item[QS_NAME].lower().endswith(' switch'):
            item[QS_TYPE] = 'switch'
            item[QS_NAME] = item[QS_NAME][:-7]

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
        if item.get(QS_CMD, '') in cmd_buttons:
            hass.bus.fire('qwikswitch.button.' + item.get(QS_ID, '@no_id'))
            return

        # Update all ha_objects
        qsreply = qsusb.devices()
        if qsreply is False:
            return
        for item in qsreply:
            if item[QS_ID] in qsusb.ha_objects:
                qsusb.ha_objects[item[QS_ID]].update_value(
                    round(min(item[PQS_VALUE], 100) * 2.55))

    qsusb.listen(callback=qs_callback, timeout=30)
    return True
