"""
Support for Qwikswitch devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/qwikswitch/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, CONF_URL)
from homeassistant.helpers.discovery import load_platform
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.switch import SwitchDevice

REQUIREMENTS = ['pyqwikswitch==0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'qwikswitch'

CONF_DIMMER_ADJUST = 'dimmer_adjust'
CONF_BUTTON_EVENTS = 'button_events'
CV_DIM_VALUE = vol.All(vol.Coerce(float), vol.Range(min=1, max=3))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL, default='http://127.0.0.1:2020'):
            vol.Coerce(str),
        vol.Optional(CONF_DIMMER_ADJUST, default=1): CV_DIM_VALUE,
        vol.Optional(CONF_BUTTON_EVENTS): vol.Coerce(str)
    })}, extra=vol.ALLOW_EXTRA)

QSUSB = {}

SUPPORT_QWIKSWITCH = SUPPORT_BRIGHTNESS


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
        QSUSB[self._id] = self

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
            super().schedule_update_ha_state()  # Part of Entity/ToggleEntity
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


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""

    pass


class QSLight(QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_QWIKSWITCH


def setup(hass, config):
    """Set up the QSUSB component."""
    from pyqwikswitch import (
        QSUsb, CMD_BUTTONS, QS_NAME, QS_ID, QS_CMD, PQS_VALUE, PQS_TYPE,
        QSType)

    # Override which cmd's in /&listen packets will fire events
    # By default only buttons of type [TOGGLE,SCENE EXE,LEVEL]
    cmd_buttons = config[DOMAIN].get(CONF_BUTTON_EVENTS, ','.join(CMD_BUTTONS))
    cmd_buttons = cmd_buttons.split(',')

    url = config[DOMAIN][CONF_URL]
    dimmer_adjust = config[DOMAIN][CONF_DIMMER_ADJUST]

    qsusb = QSUsb(url, _LOGGER, dimmer_adjust)

    def _stop(event):
        """Stop the listener queue and clean up."""
        nonlocal qsusb
        qsusb.stop()
        qsusb = None
        global QSUSB
        QSUSB = {}
        _LOGGER.info("Waiting for long poll to QSUSB to time out")

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, _stop)

    # Discover all devices in QSUSB
    devices = qsusb.devices()
    QSUSB['switch'] = []
    QSUSB['light'] = []
    for item in devices:
        if item[PQS_TYPE] == QSType.relay and (item[QS_NAME].lower()
                                               .endswith(' switch')):
            item[QS_NAME] = item[QS_NAME][:-7]  # Remove ' switch' postfix
            QSUSB['switch'].append(QSSwitch(item, qsusb))
        elif item[PQS_TYPE] in [QSType.relay, QSType.dimmer]:
            QSUSB['light'].append(QSLight(item, qsusb))
        else:
            _LOGGER.warning("Ignored unknown QSUSB device: %s", item)

    # Load platforms
    for comp_name in ('switch', 'light'):
        if QSUSB[comp_name]:
            load_platform(hass, comp_name, 'qwikswitch', {}, config)

    def qs_callback(item):
        """Typically a button press or update signal."""
        if qsusb is None:  # Shutting down
            _LOGGER.info("Button press or updating signal done")
            return

        # If button pressed, fire a hass event
        if item.get(QS_CMD, '') in cmd_buttons:
            hass.bus.fire('qwikswitch.button.' + item.get(QS_ID, '@no_id'))
            return

        # Update all ha_objects
        qsreply = qsusb.devices()
        if qsreply is False:
            return
        for itm in qsreply:
            if itm[QS_ID] in QSUSB:
                QSUSB[itm[QS_ID]].update_value(
                    round(min(itm[PQS_VALUE], 100) * 2.55))

    def _start(event):
        """Start listening."""
        qsusb.listen(callback=qs_callback, timeout=30)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start)

    return True
