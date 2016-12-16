"""
CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging

import os
import voluptuous as vol
from collections import defaultdict
from functools import reduce

from homeassistant.components import discovery
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (EVENT_HOMEASSISTANT_START, STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from pycec.datastruct import CecCommand

REQUIREMENTS = ['pyCEC>=0.0.4']

DOMAIN = 'hdmi_cec'

_LOGGER = logging.getLogger(__name__)

ICON_UNKNOWN = 'mdi:help'
ICON_AUDIO = 'mdi:speaker'
ICON_PLAYER = 'mdi:play'
ICON_TUNER = 'mdi:nest-thermostat'
ICON_RECORDER = 'mdi:microphone'
ICON_TV = 'mdi:television'

CEC_DEVICES = defaultdict(list)

CONF_EXCLUDE = 'exclude'
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_EXCLUDE, default=[]): vol.Schema([int])
    })
}, extra=vol.REMOVE_EXTRA)

CMD_UP = 'up'
CMD_DOWN = 'down'
CMD_MUTE = 'mute'
CMD_UNMUTE = 'unmute'
CMD_MUTE_TOGGLE = 'toggle mute'

EVENT_CEC_COMMAND_RECEIVED = 'cec_command_received'
EVENT_CEC_KEYPRESS_RECEIVED = 'cec_keypress_received'

SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_VOLUME = 'volume'
SERVICE_UPDATE_DEVICES = 'update'

ATTR_PHYSICAL_ADDRESS = 'physical_address'
ATTR_TYPE_ID = 'type_id'
ATTR_VENDOR_NAME = 'vendor_name'
ATTR_VENDOR_ID = 'vendor_id'
ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_TYPE = 'type'
ATTR_KEY = 'key'
ATTR_DUR = 'dur'
ATTR_SRC = 'src'
ATTR_DST = 'dst'
ATTR_CMD = 'cmd'
ATTR_ATT = 'att'
ATTR_RAW = 'raw'
ATTR_DIR = 'dir'
ATTR_ABT = 'abt'
ATTR_NEW = 'new'

SERVICE_SEND_COMMAND_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(ATTR_CMD): vol.Coerce(int),
        vol.Optional(ATTR_SRC): vol.Coerce(int),
        vol.Optional(ATTR_DST): vol.Coerce(int),
        vol.Optional(ATTR_ATT): vol.Coerce(int),
        vol.Optional(ATTR_RAW): vol.Coerce(str)
    })
}, extra=vol.REMOVE_EXTRA)

SERVICE_VOLUME_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CMD_UP): vol.Coerce(int),
        vol.Optional(CMD_DOWN): vol.Coerce(int),
        vol.Optional(CMD_MUTE): None,
        vol.Optional(CMD_UNMUTE): None,
        vol.Optional(CMD_MUTE_TOGGLE): None
    })
}, extra=vol.REMOVE_EXTRA)

SERVICE_POWER_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(ATTR_DST): vol.Coerce(int),
    })
}, extra=vol.REMOVE_EXTRA)


def setup(hass: HomeAssistant, base_config):
    """Setup CEC capability."""

    from pycec.network import HdmiNetwork
    import cec

    _LOGGER.debug("CEC setup")
    config = base_config.get(DOMAIN)

    cecconfig = cec.libcec_configuration()
    cecconfig.strDeviceName = "HA"
    cecconfig.bActivateSource = 0
    cecconfig.bMonitorOnly = 0
    cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
    cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT
    network = HdmiNetwork(config=cecconfig, loop=hass.loop)

    exclude = config.get(CONF_EXCLUDE)

    @callback
    def _volume(call):
        """Increase/decrease volume and mute/unmute system"""
        for cmd, att in call.data.items():
            att = int(att)
            att = 1 if att < 1 else att
            if cmd == CMD_UP:
                for _ in range(att):
                    hass.loop.create_task(network.async_send_command('f5:44:41'))
                hass.loop.create_task(network.async_send_command('f5:45'))
                _LOGGER.info("Volume increased %d times", att)
            elif cmd == CMD_DOWN:
                for _ in range(att):
                    hass.loop.create_task(network.async_send_command('f5:44:42'))
                hass.loop.create_task(network.async_send_command('f5:45'))
                _LOGGER.info("Volume deceased %d times", att)
            elif cmd == CMD_MUTE:
                hass.loop.create_task(network.async_send_command('f5:44:43'))
                hass.loop.create_task(network.async_send_command('f5:45'))
                _LOGGER.info("Audio muted")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    @callback
    def _tx(call):
        """Send CEC command."""
        d = call.data
        if ATTR_RAW in d:
            command = CecCommand(d[ATTR_RAW])
        else:
            if ATTR_SRC in d:
                src = d[ATTR_SRC]
            else:
                src = 0xf
            if ATTR_DST in d:
                dst = d[ATTR_DST]
            else:
                dst = cec.CECDEVICE_BROADCAST
            if ATTR_CMD in d:
                cmd = d[ATTR_CMD]
            else:
                _LOGGER.error("Attribute 'cmd' is missing")
                return False
            if ATTR_ATT in d:
                att = reduce(lambda x, y: "%s:%x" % (x, y), d[ATTR_ATT])
            else:
                att = ""
            command = CecCommand(cmd, dst, src, att)
        hass.loop.create_task(network.async_send_command(command))

    @callback
    def _update(call):
        hass.loop.create_task(network.async_scan())

    def _new_device(device):
        _LOGGER.debug("New devices callback: %s", device)
        discovery.load_platform(hass, "switch", DOMAIN, discovered={ATTR_NEW: [device]},
                                hass_config=base_config)

    def _on_init(network):
        _LOGGER.debug("Network initialized. Scanning")
        hass.loop.create_task(network.async_scan())

    def _start_cec(event):
        """Open CEC adapter."""

        _LOGGER.debug("Starting CEC")

        descriptions = load_yaml_config_file(
            os.path.join(os.path.dirname(__file__), 'services.yaml'))[DOMAIN]

        _LOGGER.debug("Registering services")
        hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, _tx, descriptions[SERVICE_SEND_COMMAND])
        hass.services.register(DOMAIN, SERVICE_VOLUME, _volume, descriptions[SERVICE_VOLUME])
        _LOGGER.debug("Registering update service")
        hass.services.register(DOMAIN, SERVICE_UPDATE_DEVICES, _update)

        _LOGGER.debug("Setting update callback")
        network.set_new_device_callback(_new_device)
        network.set_initialized_callback(_on_init)
        _LOGGER.debug("INIT")
        hass.loop.create_task(network.async_init())

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, network.stop)
    return True


def icon_by_type(cec_type):
    return ICON_TV if cec_type == 0 \
        else ICON_RECORDER if cec_type == 1 \
        else ICON_TUNER if cec_type == 3 \
        else ICON_PLAYER if cec_type == 4 \
        else ICON_AUDIO if cec_type == 5 \
        else ICON_UNKNOWN


class CecDevice(Entity):
    """Representation of a HDMI CEC device entity."""

    def __init__(self, hass: HomeAssistant, device, logical):
        """Initialize the device."""
        self._device = device
        self.hass = hass
        self._icon = None
        self._state = STATE_UNKNOWN
        self._logical_address = logical
        self.entity_id = "%s.%d" % (DOMAIN, self._logical_address)
        device.set_update_callback(self.update)

    def update(self, device=None):
        if device:
            if device.power_status == 0:
                self._state = 'on'
            elif device.power_status == 1:
                self._state = 'off'
            else:
                _LOGGER.warning("Unknown state: %d", device.power_status)
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return "%s %s" % (
            self.vendor_name, self._device.osd_name) \
            if self._device.osd_name is not None and self.vendor_name is not None and self.vendor_name != 'Unknown' \
            else "%s %d" % (self._device.type_name, self._logical_address) if self._device.osd_name is None \
            else "%s %d (%s)" % (
            self._device.type_name, self._logical_address, self._device.osd_name)

    @property
    def state(self) -> str:
        """No polling needed."""
        return self._state

    @property
    def vendor_id(self):
        return self._device.vendor_id

    @property
    def vendor_name(self):
        return self._device.vendor

    @property
    def physical_address(self):
        return str(self._device.physical_address)

    @property
    def type(self):
        return self._device.type_name

    @property
    def type_id(self):
        return self._device.type

    @property
    def icon(self):
        return icon_by_type(self._device.type) if self._icon is None else self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        if self.vendor_id is not None:
            state_attr[ATTR_VENDOR_ID] = self.vendor_id
            state_attr[ATTR_VENDOR_NAME] = self.vendor_name
        if self.type_id is not None:
            state_attr[ATTR_TYPE_ID] = self.type_id
            state_attr[ATTR_TYPE] = self.type
        if self.physical_address is not None:
            state_attr[ATTR_PHYSICAL_ADDRESS] = self.physical_address
        return state_attr
