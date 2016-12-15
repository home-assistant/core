"""
CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging

import os
import voluptuous as vol
from collections import defaultdict

from homeassistant.components import discovery
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (EVENT_HOMEASSISTANT_START, STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

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


def _init_cec(cecconfig=None):
    import cec
    lib_cec = cec.ICECAdapter.Create(cecconfig)
    adapter = None
    adapters = lib_cec.DetectAdapters()
    for adapter in adapters:
        _LOGGER.info("found a CEC adapter:")
        _LOGGER.info("port:     " + adapter.strComName)
        _LOGGER.info("product:  " + hex(adapter.iProductId))
        adapter = adapter.strComName
    if adapter is None:
        _LOGGER.warning("No adapters found")
        return None
    else:
        if lib_cec.Open(adapter):
            _LOGGER.info("connection opened")
            return lib_cec
        else:
            _LOGGER.error("failed to open a connection to the CEC adapter")
            return lib_cec


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
    network = HdmiNetwork(adapter=_init_cec(cecconfig=cecconfig), loop=hass.loop)

    exclude = config.get(CONF_EXCLUDE)

    active_devices = set()

    def _update_devices():
        new_devices = set()
        _LOGGER.debug("HA starting device update")
        for d in network.devices:
            if d.logical_address not in active_devices:
                new_devices.add(d)
        if new_devices:
            discovery.load_platform(hass, "switch", DOMAIN, discovered={ATTR_NEW: new_devices},
                                    hass_config=base_config)

    def _start_cec(event):
        """Open CEC adapter."""

        descriptions = load_yaml_config_file(
            os.path.join(os.path.dirname(__file__), 'services.yaml'))[DOMAIN]

        # hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, tx, descriptions[SERVICE_SEND_COMMAND])
        # hass.services.register(DOMAIN, SERVICE_VOLUME, volume, descriptions[SERVICE_VOLUME])
        hass.services.register(DOMAIN, SERVICE_UPDATE_DEVICES, _update_devices)

        _LOGGER.debug("Starting HDMI network")
        # network.start()
        network.scan()
        _LOGGER.debug("started HDMI network")
        hass.services.call(DOMAIN, SERVICE_UPDATE_DEVICES)

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

    def update(self):
        self._device.update_power()

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
        return self._device.physical_address

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
