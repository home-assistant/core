"""
CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import asyncio
import logging
import os
import threading
import time
from collections import defaultdict
from functools import reduce

import cec
import voluptuous as vol

from homeassistant.components import discovery
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (EVENT_HOMEASSISTANT_START, STATE_ON, STATE_OFF,
                                 STATE_UNKNOWN, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

DOMAIN = 'hdmi_cec'

_LOGGER = logging.getLogger(__name__)

CEC_CLIENT = {}

SCAN_INTERVAL = 30

VENDORS = {0x000039: 'Toshiba',
           0x0000F0: 'Samsung',
           0x0005CD: 'Denon',
           0x000678: 'Marantz',
           0x000982: 'Loewe',
           0x0009B0: 'Onkyo',
           0x000CB8: 'Medion',
           0x000CE7: 'Toshiba',
           0x001582: 'PulseEight',
           0x001950: 'HarmanKardon',
           0x001A11: 'Google',
           0x0020C7: 'Akai',
           0x002467: 'AOC',
           0x008045: 'Panasonic',
           0x00903E: 'Philips',
           0x009053: 'Daewoo',
           0x00A0DE: 'Yamaha',
           0x00D0D5: 'Grundig',
           0x00E036: 'Pioneer',
           0x00E091: 'LG',
           0x08001F: 'Sharp',
           0x080046: 'Sony',
           0x18C086: 'Broadcom',
           0x534850: 'Sharp',
           0x6B746D: 'Vizio',
           0x8065E9: 'Benq',
           0x9C645E: 'HarmanKardon',
           0: 'Unknown'}

CEC_LOGICAL_TO_TYPE = [0,  # TV0
                       1,  # Recorder 1
                       1,  # Recorder 2
                       3,  # Tuner 1
                       4,  # Playback 1
                       5,  # Audio
                       3,  # Tuner 2
                       3,  # Tuner 3
                       4,  # Playback 2
                       1,  # Recorder 3
                       3,  # Tuner 4
                       4,  # Playback 3
                       2,  # Reserved 1
                       2,  # Reserved 2
                       2,  # Free use
                       2  # Broadcast
                       ]

DEVICE_TYPE_NAMES = ["TV", "Recorder", "UNKNOWN", "Tuner", "Playback", "Audio"]

ICON_UNKNOWN = 'mdi:help'
ICON_AUDIO = 'mdi:speaker'
ICON_PLAYER = 'mdi:play'
ICON_TUNER = 'mdi:nest-thermostat'
ICON_RECORDER = 'mdi:microphone'
ICON_TV = 'mdi:television'

CEC_DEVICES = defaultdict(list)
DEVICE_PRESENCE = {}

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

SERVICE_POWER_ON = 'turn_on'
SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_STANDBY = 'turn_off'
SERVICE_SELF = 'self'
SERVICE_VOLUME = 'volume'

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


def setup(hass, base_config):
    """Setup CEC capability."""

    _LOGGER.debug("CEC setup")
    config = base_config.get(DOMAIN)

    global CEC_CLIENT
    CEC_CLIENT = CecClient(hass)
    exclude = config.get(CONF_EXCLUDE)
    stop = threading.Event()

    def _start_cec(event):
        """Open CEC adapter."""
        # initialise libCEC and enter the main loop
        if CEC_CLIENT.init_lib_cec():
            descriptions = load_yaml_config_file(
                os.path.join(os.path.dirname(__file__), 'services.yaml'))[DOMAIN]

            hass.services.register(DOMAIN, SERVICE_POWER_ON, CEC_CLIENT.power_on, descriptions[SERVICE_POWER_ON])
            hass.services.register(DOMAIN, SERVICE_STANDBY, CEC_CLIENT.standby, descriptions[SERVICE_STANDBY])
            hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, CEC_CLIENT.tx, descriptions[SERVICE_SEND_COMMAND])
            hass.services.register(DOMAIN, SERVICE_VOLUME, CEC_CLIENT.volume, descriptions[SERVICE_VOLUME])
            hass.add_job(_start_discovery)
            return True
        else:
            return False

    def _do_discovery(devices, device):
        _LOGGER.info("CEC discovering device %d", device)
        if CEC_CLIENT.poll(device):
            _LOGGER.info("CEC found device %d", device)
            devices.add(device)

    def _start_discovery():
        dev_type = 'switch'

        new_devices = set()
        while True:
            for device in filter(lambda x: exclude is None or x not in exclude,
                                 filter(lambda x: x not in DEVICE_PRESENCE or not DEVICE_PRESENCE[x],
                                        range(15))):
                hass.add_job(_do_discovery, new_devices, device)

            seconds_since_scan = 0
            while seconds_since_scan < SCAN_INTERVAL:
                if stop.is_set():
                    return
                time.sleep(1)
                seconds_since_scan += 1

            if new_devices:
                to_add = new_devices
                discovery.load_platform(hass, dev_type, DOMAIN, discovered={ATTR_NEW: to_add},
                                        hass_config=base_config)
                new_devices -= to_add

    def _stop_cec(event):
        stop.set()
        CEC_CLIENT.lib_cec.Close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_cec)
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

    def __init__(self, hass, cec_client, logical):
        """Initialize the device."""
        self.hass = hass
        self._icon = None
        self._state = STATE_UNKNOWN
        self._physical_address = None
        self._logical_address = logical
        self._vendor_id = None
        self._cec_type_id = None
        self._cec_type_id = CEC_LOGICAL_TO_TYPE[logical]
        self._available = False
        self._hidden = False
        self._name = None
        DEVICE_PRESENCE[logical] = True
        _LOGGER.info("Initializing CEC device %s", self.name)
        self.cec_client = cec_client
        hass.bus.listen(EVENT_CEC_COMMAND_RECEIVED, self._update_callback)
        self.entity_id = "%s.%d" % (DOMAIN, self._logical_address)

    @asyncio.coroutine
    def async_update(self):
        yield from self.async_update_availability()
        if self.available:
            _LOGGER.info("Updating status for device %s", hex(self._logical_address)[2:])
            yield from self.async_request_cec_power_status()
            yield from self.async_request_cec_osd_name()
            yield from self.async_request_cec_vendor()
            yield from self.async_request_physical_address()
        else:
            _LOGGER.info("device not available. Not updating")

    @asyncio.coroutine
    def async_update_availability(self):
        self._available = self.cec_client.poll(self._logical_address)
        if not self._available:
            self.hass.async_add_job(self.remove)
            DEVICE_PRESENCE[self._logical_address] = False
            self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_request_physical_address(self):
        self.hass.add_job(self.cec_client.tx,
                          type('call', (object,), {'data': {ATTR_DST: self._logical_address, ATTR_CMD: 0x83}}))

    @asyncio.coroutine
    def async_request_cec_vendor(self):
        self.hass.add_job(self.cec_client.tx,
                          type('call', (object,), {'data': {ATTR_DST: self._logical_address, ATTR_CMD: 0x8C}}))

    @asyncio.coroutine
    def async_request_cec_osd_name(self):
        self.hass.add_job(self.cec_client.tx,
                          type('call', (object,), {'data': {ATTR_DST: self._logical_address, ATTR_CMD: 0x46}}))

    @asyncio.coroutine
    def async_request_cec_power_status(self):
        self.hass.add_job(self.cec_client.tx,
                          type('call', (object,), {'data': {ATTR_DST: self._logical_address, ATTR_CMD: 0x8F}}))

    @callback
    def _update_callback(self, event):
        if ATTR_CMD not in event.data or ATTR_SRC not in event.data:
            return
        cmd = event.data[ATTR_CMD]
        src = event.data[ATTR_SRC]
        dst = event.data[ATTR_DST] if ATTR_DST in event.data else None
        cmd_chain = event.data[ATTR_ATT] if ATTR_ATT in event.data else []
        if src == self._logical_address:
            if cmd == 0x90:
                status = cmd_chain[0]
                if status == 0x00:
                    self._state = STATE_ON
                elif status == 0x01:
                    self._state = STATE_OFF
                else:
                    self._state = STATE_UNKNOWN
                _LOGGER.info("Got status for device %x -> %x, %s", src, dst, self._state)
            elif cmd == 0x47:
                self._name = ''
                for c in cmd_chain:
                    self._name += chr(c)
                _LOGGER.info("Got name for device %x -> %x, %s", src, dst, self._name)
            elif cmd == 0x87:
                self._vendor_id = 0
                for i in cmd_chain:
                    self._vendor_id *= 0x100
                    self._vendor_id += i
                _LOGGER.info("Got vendor for device %x -> %x, %s: %s", src, dst, self.vendor_id, self.vendor_name)
            elif cmd == 0x84:
                self._physical_address = "%d.%d.%d.%d" % (
                    cmd_chain[0] / 0x10, cmd_chain[0] % 0x10, cmd_chain[1] / 0x10, cmd_chain[1] % 0x10)
                self._cec_type_id = cmd_chain[2]
                _LOGGER.info("Got physical address and type for device %x -> %x, %s, %s",
                             src, dst, self._physical_address, self.type)

            self.schedule_update_ha_state(False)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the device."""
        return "%s %s" % (self.vendor_name, self._name) if self._name is not None and self.vendor_name is not None \
            and self.vendor_name != 'Unknown' \
            else "%s %d" % (DEVICE_TYPE_NAMES[self._cec_type_id], self._logical_address) if self._name is None \
            else "%s %d (%s)" % (
            DEVICE_TYPE_NAMES[self._cec_type_id], self._logical_address, self._name)

    @property
    def state(self):
        """No polling needed."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        return attr

    @property
    def vendor_id(self):
        return self._vendor_id

    @property
    def vendor_name(self):
        return VENDORS[self._vendor_id] if self._vendor_id in VENDORS else VENDORS[0]

    @property
    def physical_address(self):
        return self._physical_address

    @property
    def type(self):
        return DEVICE_TYPE_NAMES[self._cec_type_id]

    @property
    def type_id(self):
        return self._cec_type_id

    @property
    def icon(self):
        return icon_by_type(self._cec_type_id) if self._icon is None else self._icon

    @property
    def hidden(self):
        return self._hidden or not self.available

    @property
    def available(self):
        return self._available

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


def addr_from_data(call, addr):
    return cec.CECDEVICE_BROADCAST if call.data is None or addr not in call.data or call.data[addr] is None else \
        call.data[addr]


class CecClient:
    cecconfig = {}
    lib_cec = {}
    hass = {}
    callbacks = []

    def init_lib_cec(self):
        """initialise libCEC"""
        self.lib_cec = cec.ICECAdapter.Create(self.cecconfig)
        # print libCEC version and compilation information
        _LOGGER.info("libCEC version " + self.lib_cec.VersionToString(
            self.cecconfig.serverVersion) + " loaded: " + self.lib_cec.GetLibInfo())

        # search for adapters
        adapter = None
        adapters = self.lib_cec.DetectAdapters()
        for adapter in adapters:
            _LOGGER.info("found a CEC adapter:")
            _LOGGER.info("port:     " + adapter.strComName)
            _LOGGER.info("vendor:   " + hex(adapter.iVendorId))
            _LOGGER.info("product:  " + hex(adapter.iProductId))
            adapter = adapter.strComName
        if adapter is None:
            _LOGGER.info("No adapters found")
            return False
        else:
            if self.lib_cec.Open(adapter):
                # self.lib_cec.GetCurrentConfiguration(self.cecconfig)
                _LOGGER.info("connection opened")
                return True
            else:
                _LOGGER.info("failed to open a connection to the CEC adapter")
                return False

    def get_logical_address(self):
        return self.cecconfig.logicalAddresses.primary

    def standby(self, call):
        """send a standby command"""
        self.lib_cec.StandbyDevices(addr_from_data(call, ATTR_DST))

    def power_on(self, call):
        self.lib_cec.PowerOnDevices(addr_from_data(call, ATTR_DST))

    def volume(self, call):
        for cmd, att in call.data.items():
            att = int(att)
            att = 1 if att < 1 else att
            if cmd == CMD_UP:
                for _ in range(att):
                    self.send_command('%x5:44:41' % self.get_logical_address())
                self.send_command('%x5:45' % self.get_logical_address())
                _LOGGER.info("Volume increased %d times", att)
            elif cmd == CMD_DOWN:
                for _ in range(att):
                    self.send_command('%x5:44:42' % self.get_logical_address())
                self.send_command('%x5:45' % self.get_logical_address())
                _LOGGER.info("Volume deceased %d times", att)
            elif cmd == CMD_MUTE:
                self.lib_cec.AudioMute()
                _LOGGER.info("Audio muted")
            elif cmd == CMD_UNMUTE:
                self.lib_cec.AudioUnmute()
                _LOGGER.info("Audio unmuted")
            elif cmd == CMD_MUTE_TOGGLE:
                self.lib_cec.AudioToggleMute()
                _LOGGER.info("Audio mute toggled")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    def tx(self, call):
        """Send CEC command."""
        d = call.data
        if ATTR_RAW in d:
            command = d[ATTR_RAW]
        else:
            if ATTR_SRC in d:
                src = d[ATTR_SRC]
            else:
                src = self.get_logical_address()
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
            command = "%x%x:%x%s" % (src, dst, cmd, att)
        self.send_command(command)

    def send_command(self, data):
        """send a custom command to cec adapter"""
        cmd = self.lib_cec.CommandFromString(data)
        _LOGGER.info("transmit " + data)
        if not self.lib_cec.Transmit(cmd):
            _LOGGER.warning("failed to send command")

    def poll(self, device_id):
        return self.lib_cec.PollDevice(device_id)

    def cec_key_press_callback(self, key, duration):
        """key press callback"""
        _LOGGER.info("[key pressed] " + str(key))
        self.hass.bus.fire(EVENT_CEC_KEYPRESS_RECEIVED, {ATTR_KEY: key, ATTR_DUR: duration})
        return 0

    def cec_command_callback(self, command):
        """command received callback"""
        params = {ATTR_DIR: command[:2]}
        command = command[3:]
        params[ATTR_RAW] = command
        cmd_chain = command.split(':')
        addr = cmd_chain.pop(0)
        params[ATTR_SRC] = int(addr[0], 16)
        params[ATTR_DST] = int(addr[1], 16)
        cmd_chain = list(map(lambda x: int(x, 16), cmd_chain))
        params[ATTR_CMD] = cmd_chain.pop(0)
        if params[ATTR_CMD] == 00:
            params[ATTR_ABT] = True
            params[ATTR_CMD] = cmd_chain.pop(0)
        else:
            params[ATTR_ABT] = False
        params[ATTR_ATT] = cmd_chain

        self.hass.bus.fire(EVENT_CEC_COMMAND_RECEIVED, params)
        return 0

    def __init__(self, hass):
        self.cecconfig = cec.libcec_configuration()
        self.cecconfig.strDeviceName = "HA"
        self.cecconfig.bActivateSource = 0
        self.cecconfig.bMonitorOnly = 0
        self.cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
        self.cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT
        self.cecconfig.strDeviceLanguage = "cze"
        self.hass = hass
        self.cecconfig.SetKeyPressCallback(self.cec_key_press_callback)
        self.cecconfig.SetCommandCallback(self.cec_command_callback)
