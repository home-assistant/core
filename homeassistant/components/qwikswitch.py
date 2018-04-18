"""
Support for Qwikswitch devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/qwikswitch/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, CONF_URL,
    CONF_SENSORS, CONF_SWITCHES)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity
from homeassistant.components.light import ATTR_BRIGHTNESS
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyqwikswitch==0.6']

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
        vol.Optional(CONF_BUTTON_EVENTS, default=[]): cv.ensure_list_csv,
        vol.Optional(CONF_SENSORS, default={}): vol.Schema({cv.slug: str}),
        vol.Optional(CONF_SWITCHES, default=[]): vol.All(
            cv.ensure_list, [str])
    })}, extra=vol.ALLOW_EXTRA)


class QSToggleEntity(Entity):
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
        self.qsid = qsid
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
        return self._qsusb[self.qsid, 1] > 0

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        new = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._qsusb.set_value(self.qsid, new)

    async def async_turn_off(self, **_):
        """Turn the device off."""
        self._qsusb.set_value(self.qsid, 0)

    def _update(self, _packet=None):
        """Schedule an update - match dispather_send signature."""
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Listen for updates from QSUSb via dispatcher."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            self.qsid, self._update)


async def async_setup(hass, config):
    """Qwiskswitch component setup."""
    from pyqwikswitch.async_ import QSUsb
    from pyqwikswitch import (
        CMD_BUTTONS, QS_CMD, QS_ID, QS_TYPE, QSType)

    # Add cmd's to in /&listen packets will fire events
    # By default only buttons of type [TOGGLE,SCENE EXE,LEVEL]
    cmd_buttons = set(CMD_BUTTONS)
    for btn in config[DOMAIN][CONF_BUTTON_EVENTS]:
        cmd_buttons.add(btn)

    url = config[DOMAIN][CONF_URL]
    dimmer_adjust = config[DOMAIN][CONF_DIMMER_ADJUST]
    sensors = config[DOMAIN]['sensors']
    switches = config[DOMAIN]['switches']

    def callback_value_changed(_qsd, qsid, _val):
        """Update entity values based on device change."""
        _LOGGER.debug("Dispatch %s (update from devices)", qsid)
        hass.helpers.dispatcher.async_dispatcher_send(qsid, None)

    session = async_get_clientsession(hass)
    qsusb = QSUsb(url=url, dim_adj=dimmer_adjust, session=session,
                  callback_value_changed=callback_value_changed)

    # Discover all devices in QSUSB
    if not await qsusb.update_from_devices():
        return False

    hass.data[DOMAIN] = qsusb

    _new = {'switch': [], 'light': [], 'sensor': sensors}
    for _id, item in qsusb.devices:
        if _id in switches:
            if item[QS_TYPE] != QSType.relay:
                _LOGGER.warning(
                    "You specified a switch that is not a relay %s", _id)
                continue
            _new['switch'].append(_id)
        elif item[QS_TYPE] in [QSType.relay, QSType.dimmer]:
            _new['light'].append(_id)
        else:
            _LOGGER.warning("Ignored unknown QSUSB device: %s", item)
            continue

    # Load platforms
    for comp_name, comp_conf in _new.items():
        if comp_conf:
            load_platform(hass, comp_name, DOMAIN, {DOMAIN: comp_conf}, config)

    def callback_qs_listen(item):
        """Typically a button press or update signal."""
        # If button pressed, fire a hass event
        if QS_ID in item:
            if item.get(QS_CMD, '') in cmd_buttons:
                hass.bus.async_fire(
                    'qwikswitch.button.{}'.format(item[QS_ID]), item)
                return

            # Private method due to bad __iter__ design in qsusb
            # qsusb.devices returns a list of tuples
            if item[QS_ID] not in \
                    qsusb.devices._data:  # pylint: disable=protected-access
                # Not a standard device in, component can handle packet
                # i.e. sensors
                _LOGGER.debug("Dispatch %s ((%s))", item[QS_ID], item)
                hass.helpers.dispatcher.async_dispatcher_send(
                    item[QS_ID], item)

        # Update all ha_objects
        hass.async_add_job(qsusb.update_from_devices)

    @callback
    def async_start(_):
        """Start listening."""
        hass.async_add_job(qsusb.listen, callback_qs_listen)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_start)

    @callback
    def async_stop(_):
        """Stop the listener queue and clean up."""
        hass.data[DOMAIN].stop()
        _LOGGER.info("Waiting for long poll to QSUSB to time out (max 30sec)")

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_stop)

    return True
