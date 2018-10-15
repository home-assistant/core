"""
HDMI CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging
import multiprocessing
from collections import defaultdict
from functools import reduce

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.const import (EVENT_HOMEASSISTANT_START, STATE_UNKNOWN,
                                 EVENT_HOMEASSISTANT_STOP, STATE_ON,
                                 STATE_OFF, CONF_DEVICES, CONF_PLATFORM,
                                 STATE_PLAYING, STATE_IDLE,
                                 STATE_PAUSED, CONF_HOST)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyCEC==0.4.13']

DOMAIN = 'hdmi_cec'

_LOGGER = logging.getLogger(__name__)

DEFAULT_DISPLAY_NAME = "HA"
CONF_TYPES = 'types'

ICON_UNKNOWN = 'mdi:help'
ICON_AUDIO = 'mdi:speaker'
ICON_PLAYER = 'mdi:play'
ICON_TUNER = 'mdi:radio'
ICON_RECORDER = 'mdi:microphone'
ICON_TV = 'mdi:television'
ICONS_BY_TYPE = {
    0: ICON_TV,
    1: ICON_RECORDER,
    3: ICON_TUNER,
    4: ICON_PLAYER,
    5: ICON_AUDIO
}

CEC_DEVICES = defaultdict(list)

CMD_UP = 'up'
CMD_DOWN = 'down'
CMD_MUTE = 'mute'
CMD_UNMUTE = 'unmute'
CMD_MUTE_TOGGLE = 'toggle mute'
CMD_PRESS = 'press'
CMD_RELEASE = 'release'

EVENT_CEC_COMMAND_RECEIVED = 'cec_command_received'
EVENT_CEC_KEYPRESS_RECEIVED = 'cec_keypress_received'

ATTR_PHYSICAL_ADDRESS = 'physical_address'
ATTR_TYPE_ID = 'type_id'
ATTR_VENDOR_NAME = 'vendor_name'
ATTR_VENDOR_ID = 'vendor_id'
ATTR_DEVICE = 'device'
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
ATTR_ON = 'on'
ATTR_OFF = 'off'
ATTR_TOGGLE = 'toggle'

_VOL_HEX = vol.Any(vol.Coerce(int), lambda x: int(x, 16))

SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CMD): _VOL_HEX,
    vol.Optional(ATTR_SRC): _VOL_HEX,
    vol.Optional(ATTR_DST): _VOL_HEX,
    vol.Optional(ATTR_ATT): _VOL_HEX,
    vol.Optional(ATTR_RAW): vol.Coerce(str)
}, extra=vol.PREVENT_EXTRA)

SERVICE_VOLUME = 'volume'
SERVICE_VOLUME_SCHEMA = vol.Schema({
    vol.Optional(CMD_UP): vol.Any(CMD_PRESS, CMD_RELEASE, vol.Coerce(int)),
    vol.Optional(CMD_DOWN): vol.Any(CMD_PRESS, CMD_RELEASE, vol.Coerce(int)),
    vol.Optional(CMD_MUTE): vol.Any(ATTR_ON, ATTR_OFF, ATTR_TOGGLE),
}, extra=vol.PREVENT_EXTRA)

SERVICE_UPDATE_DEVICES = 'update'
SERVICE_UPDATE_DEVICES_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({})
}, extra=vol.PREVENT_EXTRA)

SERVICE_SELECT_DEVICE = 'select_device'

SERVICE_POWER_ON = 'power_on'
SERVICE_STANDBY = 'standby'

# pylint: disable=unnecessary-lambda
DEVICE_SCHEMA = vol.Schema({
    vol.All(cv.positive_int):
        vol.Any(lambda devices: DEVICE_SCHEMA(devices), cv.string)
})

CONF_DISPLAY_NAME = 'osd_name'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVICES):
            vol.Any(DEVICE_SCHEMA, vol.Schema({
                vol.All(cv.string): vol.Any(cv.string)})),
        vol.Optional(CONF_PLATFORM): vol.Any(SWITCH, MEDIA_PLAYER),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DISPLAY_NAME): cv.string,
        vol.Optional(CONF_TYPES, default={}):
        vol.Schema({cv.entity_id: vol.Any(MEDIA_PLAYER, SWITCH)})
    })
}, extra=vol.ALLOW_EXTRA)


def pad_physical_address(addr):
    """Right-pad a physical address."""
    return addr + [0] * (4 - len(addr))


def parse_mapping(mapping, parents=None):
    """Parse configuration device mapping."""
    if parents is None:
        parents = []
    for addr, val in mapping.items():
        if isinstance(addr, (str,)) and isinstance(val, (str,)):
            from pycec.network import PhysicalAddress
            yield (addr, PhysicalAddress(val))
        else:
            cur = parents + [addr]
            if isinstance(val, dict):
                yield from parse_mapping(val, cur)
            elif isinstance(val, str):
                yield (val, pad_physical_address(cur))


def setup(hass: HomeAssistant, base_config):
    """Set up the CEC capability."""
    from pycec.network import HDMINetwork
    from pycec.commands import CecCommand, KeyReleaseCommand, KeyPressCommand
    from pycec.const import KEY_VOLUME_UP, KEY_VOLUME_DOWN, KEY_MUTE_ON, \
        KEY_MUTE_OFF, KEY_MUTE_TOGGLE, ADDR_AUDIOSYSTEM, ADDR_BROADCAST, \
        ADDR_UNREGISTERED
    from pycec.cec import CecAdapter
    from pycec.tcp import TcpAdapter

    # Parse configuration into a dict of device name to physical address
    # represented as a list of four elements.
    device_aliases = {}
    devices = base_config[DOMAIN].get(CONF_DEVICES, {})
    _LOGGER.debug("Parsing config %s", devices)
    device_aliases.update(parse_mapping(devices))
    _LOGGER.debug("Parsed devices: %s", device_aliases)

    platform = base_config[DOMAIN].get(CONF_PLATFORM, SWITCH)

    loop = (
        # Create own thread if more than 1 CPU
        hass.loop if multiprocessing.cpu_count() < 2 else None)
    host = base_config[DOMAIN].get(CONF_HOST, None)
    display_name = base_config[DOMAIN].get(
        CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    if host:
        adapter = TcpAdapter(host, name=display_name, activate_source=False)
    else:
        adapter = CecAdapter(name=display_name[:12], activate_source=False)
    hdmi_network = HDMINetwork(adapter, loop=loop)

    def _volume(call):
        """Increase/decrease volume and mute/unmute system."""
        mute_key_mapping = {ATTR_TOGGLE: KEY_MUTE_TOGGLE, ATTR_ON: KEY_MUTE_ON,
                            ATTR_OFF: KEY_MUTE_OFF}
        for cmd, att in call.data.items():
            if cmd == CMD_UP:
                _process_volume(KEY_VOLUME_UP, att)
            elif cmd == CMD_DOWN:
                _process_volume(KEY_VOLUME_DOWN, att)
            elif cmd == CMD_MUTE:
                hdmi_network.send_command(
                    KeyPressCommand(mute_key_mapping[att],
                                    dst=ADDR_AUDIOSYSTEM))
                hdmi_network.send_command(
                    KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
                _LOGGER.info("Audio muted")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    def _process_volume(cmd, att):
        if isinstance(att, (str,)):
            att = att.strip()
        if att == CMD_PRESS:
            hdmi_network.send_command(
                KeyPressCommand(cmd, dst=ADDR_AUDIOSYSTEM))
        elif att == CMD_RELEASE:
            hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
        else:
            att = 1 if att == "" else int(att)
            for _ in range(0, att):
                hdmi_network.send_command(
                    KeyPressCommand(cmd, dst=ADDR_AUDIOSYSTEM))
                hdmi_network.send_command(
                    KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))

    def _tx(call):
        """Send CEC command."""
        data = call.data
        if ATTR_RAW in data:
            command = CecCommand(data[ATTR_RAW])
        else:
            if ATTR_SRC in data:
                src = data[ATTR_SRC]
            else:
                src = ADDR_UNREGISTERED
            if ATTR_DST in data:
                dst = data[ATTR_DST]
            else:
                dst = ADDR_BROADCAST
            if ATTR_CMD in data:
                cmd = data[ATTR_CMD]
            else:
                _LOGGER.error("Attribute 'cmd' is missing")
                return False
            if ATTR_ATT in data:
                if isinstance(data[ATTR_ATT], (list,)):
                    att = data[ATTR_ATT]
                else:
                    att = reduce(lambda x, y: "%s:%x" % (x, y), data[ATTR_ATT])
            else:
                att = ""
            command = CecCommand(cmd, dst, src, att)
        hdmi_network.send_command(command)

    def _standby(call):
        hdmi_network.standby()

    def _power_on(call):
        hdmi_network.power_on()

    def _select_device(call):
        """Select the active device."""
        from pycec.network import PhysicalAddress

        addr = call.data[ATTR_DEVICE]
        if not addr:
            _LOGGER.error("Device not found: %s", call.data[ATTR_DEVICE])
            return
        if addr in device_aliases:
            addr = device_aliases[addr]
        else:
            entity = hass.states.get(addr)
            _LOGGER.debug("Selecting entity %s", entity)
            if entity is not None:
                addr = entity.attributes['physical_address']
                _LOGGER.debug("Address acquired: %s", addr)
                if addr is None:
                    _LOGGER.error("Device %s has not physical address",
                                  call.data[ATTR_DEVICE])
                    return
        if not isinstance(addr, (PhysicalAddress,)):
            addr = PhysicalAddress(addr)
        hdmi_network.active_source(addr)
        _LOGGER.info("Selected %s (%s)", call.data[ATTR_DEVICE], addr)

    def _update(call):
        """
        Update if device update is needed.

        Called by service, requests CEC network to update data.
        """
        hdmi_network.scan()

    def _new_device(device):
        """Handle new devices which are detected by HDMI network."""
        key = '{}.{}'.format(DOMAIN, device.name)
        hass.data[key] = device
        ent_platform = base_config[DOMAIN][CONF_TYPES].get(key, platform)
        discovery.load_platform(
            hass, ent_platform, DOMAIN, discovered={ATTR_NEW: [key]},
            hass_config=base_config)

    def _shutdown(call):
        hdmi_network.stop()

    def _start_cec(event):
        """Register services and start HDMI network to watch for devices."""
        hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, _tx,
                               SERVICE_SEND_COMMAND_SCHEMA)
        hass.services.register(DOMAIN, SERVICE_VOLUME, _volume,
                               schema=SERVICE_VOLUME_SCHEMA)
        hass.services.register(DOMAIN, SERVICE_UPDATE_DEVICES, _update,
                               schema=SERVICE_UPDATE_DEVICES_SCHEMA)
        hass.services.register(DOMAIN, SERVICE_POWER_ON, _power_on)
        hass.services.register(DOMAIN, SERVICE_STANDBY, _standby)
        hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE, _select_device)

        hdmi_network.set_new_device_callback(_new_device)
        hdmi_network.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    return True


class CecDevice(Entity):
    """Representation of a HDMI CEC device entity."""

    def __init__(self, hass: HomeAssistant, device, logical) -> None:
        """Initialize the device."""
        self._device = device
        self.hass = hass
        self._icon = None
        self._state = STATE_UNKNOWN
        self._logical_address = logical
        self.entity_id = "%s.%d" % (DOMAIN, self._logical_address)
        device.set_update_callback(self._update)

    def update(self):
        """Update device status."""
        self._update()

    def _update(self, device=None):
        """Update device status."""
        if device:
            from pycec.const import STATUS_PLAY, STATUS_STOP, STATUS_STILL, \
                POWER_OFF, POWER_ON
            if device.power_status == POWER_OFF:
                self._state = STATE_OFF
            elif device.status == STATUS_PLAY:
                self._state = STATE_PLAYING
            elif device.status == STATUS_STOP:
                self._state = STATE_IDLE
            elif device.status == STATUS_STILL:
                self._state = STATE_PAUSED
            elif device.power_status == POWER_ON:
                self._state = STATE_ON
            else:
                _LOGGER.warning("Unknown state: %d", device.power_status)
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return (
            "%s %s" % (self.vendor_name, self._device.osd_name)
            if (self._device.osd_name is not None and
                self.vendor_name is not None and self.vendor_name != 'Unknown')
            else "%s %d" % (self._device.type_name, self._logical_address)
            if self._device.osd_name is None
            else "%s %d (%s)" % (self._device.type_name, self._logical_address,
                                 self._device.osd_name))

    @property
    def vendor_id(self):
        """Return the ID of the device's vendor."""
        return self._device.vendor_id

    @property
    def vendor_name(self):
        """Return the name of the device's vendor."""
        return self._device.vendor

    @property
    def physical_address(self):
        """Return the physical address of device in HDMI network."""
        return str(self._device.physical_address)

    @property
    def type(self):
        """Return a string representation of the device's type."""
        return self._device.type_name

    @property
    def type_id(self):
        """Return the type ID of device."""
        return self._device.type

    @property
    def icon(self):
        """Return the icon for device by its type."""
        return (self._icon if self._icon is not None else
                ICONS_BY_TYPE.get(self._device.type)
                if self._device.type in ICONS_BY_TYPE else ICON_UNKNOWN)

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
