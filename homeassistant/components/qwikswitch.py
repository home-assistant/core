"""
Support for Qwikswitch devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/qwikswitch/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, CONF_URL)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import load_platform
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.switch import SwitchDevice

REQUIREMENTS = ['pyqwikswitch==0.5']

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

    def __init__(self, qsid, qsusb):
        """Initialize the ToggleEntity."""
        from pyqwikswitch import (QS_NAME, QSDATA, QS_TYPE, QSType)
        self._id = qsid
        self._qsusb = qsusb.devices
        dev = qsusb.devices[qsid]
        self._dim = dev[QS_TYPE] == QSType.dimmer
        self._name = dev[QSDATA][QS_NAME]

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
        return self._qsusb[self._id, 1] > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        new = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._qsusb.set_value(self._id, new)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        new = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._qsusb.set_value(self._id, new)

    def turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn the device off."""
        self._qsusb.set_value(self._id, 0)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn the device off."""
        self._qsusb.set_value(self._id, 0)


class QSSwitch(QSToggleEntity, SwitchDevice):
    """Switch based on a Qwikswitch relay module."""

    pass


class QSLight(QSToggleEntity, Light):
    """Light based on a Qwikswitch relay/dimmer module."""

    @property
    def brightness(self):
        """Return the brightness of this light (0-255)."""
        return self._qsusb[self._id, 1] if self._dim else None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS if self._dim else None


@asyncio.coroutine
def async_setup(hass, config):
    """Setup qwiskswitch component."""
    from pyqwikswitch.async import QSUsb
    from pyqwikswitch import (
        CMD_BUTTONS, QS_CMD, QSDATA, QS_ID, QS_NAME, QS_TYPE, QSType)

    hass.data[DOMAIN] = {}

    # Override which cmd's in /&listen packets will fire events
    # By default only buttons of type [TOGGLE,SCENE EXE,LEVEL]
    cmd_buttons = config[DOMAIN].get(CONF_BUTTON_EVENTS, ','.join(CMD_BUTTONS))
    cmd_buttons = cmd_buttons.split(',')

    url = config[DOMAIN][CONF_URL]
    dimmer_adjust = config[DOMAIN][CONF_DIMMER_ADJUST]

    def callback_value_changed(qsdevices, key, new): \
            # pylint: disable=unused-argument
        """Update entiry values based on device change."""
        entity = hass.data[DOMAIN].get(key)
        if entity is not None:
            entity.schedule_update_ha_state()  # Part of Entity/ToggleEntity

    session = async_get_clientsession(hass)
    qsusb = QSUsb(url=url, dim_adj=dimmer_adjust, session=session,
                  callback_value_changed=callback_value_changed)

    @callback
    def async_stop(event):  # pylint: disable=unused-argument
        """Stop the listener queue and clean up."""
        nonlocal qsusb
        qsusb.stop()
        qsusb = None
        hass.data[DOMAIN] = {}
        _LOGGER.info("Waiting for long poll to QSUSB to time out")

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_stop)

    # Discover all devices in QSUSB
    yield from qsusb.update_from_devices()
    hass.data[DOMAIN]['switch'] = []
    hass.data[DOMAIN]['light'] = []
    for _id, item in qsusb.devices:
        if (item[QS_TYPE] == QSType.relay and
                item[QSDATA][QS_NAME].lower().endswith(' switch')):
            item[QSDATA][QS_NAME] = item[QSDATA][QS_NAME][:-7]  # Remove switch
            new_dev = QSSwitch(_id, qsusb)
            hass.data[DOMAIN]['switch'].append(new_dev)
        elif item[QS_TYPE] in [QSType.relay, QSType.dimmer]:
            new_dev = QSLight(_id, qsusb)
            hass.data[DOMAIN]['light'].append(new_dev)
        else:
            _LOGGER.warning("Ignored unknown QSUSB device: %s", item)
            continue
        hass.data[DOMAIN][_id] = new_dev

    # Load platforms
    for comp_name in ('switch', 'light'):
        if hass.data[DOMAIN][comp_name]:
            load_platform(hass, comp_name, 'qwikswitch', {}, config)

    def callback_qs_listen(item):
        """Typically a button press or update signal."""
        if qsusb is None:  # Shutting down
            return

        # If button pressed, fire a hass event
        if item.get(QS_CMD, '') in cmd_buttons and QS_ID in item:
            hass.bus.async_fire('qwikswitch.button.{}'.format(item[QS_ID]))
            return

        # Update all ha_objects
        hass.async_add_job(qsusb.update_from_devices)

    @callback
    def async_start(event):  # pylint: disable=unused-argument
        """Start listening."""
        hass.async_add_job(qsusb.listen, callback_qs_listen)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_start)

    return True
