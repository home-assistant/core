"""
CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import asyncio
import logging

import cec
import voluptuous as vol
import yaml
from collections import defaultdict

import homeassistant.helpers.config_validation as cv
from homeassistant.components import discovery
from homeassistant.const import (EVENT_HOMEASSISTANT_START, CONF_DEVICES, STATE_ON, STATE_OFF,
                                 STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CEC_CLIENT = {}

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_TYPE = 'type'
ATTR_KEY = 'key'
ATTR_DURATION = 'duration'
ATTR_SRC = 'src'
ATTR_DST = 'dst'
ATTR_CMD = 'cmd'
ATTR_ATT = 'att'
ATTR_RAW = 'raw'

CMD_UP = 'up'
CMD_DOWN = 'down'
CMD_MUTE = 'mute'
CMD_UNMUTE = 'unmute'
CMD_MUTE_TOGGLE = 'toggle mute'

EVENT_CEC_COMMAND_RECEIVED = 'cec_command_received'
EVENT_CEC_KEYPRESS_RECEIVED = 'cec_keypress_received'

DOMAIN = 'hdmi_cec'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

MAX_DEPTH = 4

SERVICE_POWER_ON = 'turn_on'
SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_STANDBY = 'turn_off'
SERVICE_SELF = 'self'
SERVICE_VOLUME = 'volume'

VENDORS = {0x000039: 'Toshiba',
           0x0000F0: 'Samsung',
           0x0005CD: 'Denon',
           0x000678: 'Marantz',
           0x000982: 'Loewe',
           0x0009B0: 'Onkyo',
           0x000CB8: 'Medion',
           0x000CE7: 'Toshiba2',
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

deviceTypeNames = ["TV", "Recorder", "UNKNOWN", "Tuner", "Playback", "Audio"]

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
CEC_TYPE_TO_COMPONENT = ['media_player', 'media_player', 'switch', 'media_player', 'media_player', 'media_player']

CEC_DEVICES = defaultdict(list)

# pylint: disable=unnecessary-lambda
DEVICE_SCHEMA = vol.Schema({
    vol.All(cv.positive_int): vol.Any(lambda devices: DEVICE_SCHEMA(devices), cv.string)
})

CONF_EXCLUDE = 'exclude'
CEC_ID_LIST_SCHEMA = vol.Schema([int])
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICES): DEVICE_SCHEMA,
        vol.Optional(CONF_EXCLUDE, default=[]): CEC_ID_LIST_SCHEMA

    })
}, extra=vol.ALLOW_EXTRA)


def parse_mapping(mapping, parents=None):
    """Parse configuration device mapping."""
    if parents is None:
        parents = []
    for addr, val in mapping.items():
        cur = parents + [str(addr)]
        if isinstance(val, dict):
            yield from parse_mapping(val, cur)
        elif isinstance(val, str):
            yield (val, cur)


def pad_physical_address(addr):
    """Right-pad a physical address."""
    return addr + ['0'] * (MAX_DEPTH - len(addr))


def setup(hass, base_config):
    """Setup CEC capability."""

    _LOGGER.debug("CEC setup")
    config = base_config.get(DOMAIN)

    # Parse configuration into a dict of device name to physical address
    # represented as a list of four elements.
    flat = {}
    for pair in parse_mapping(config.get(CONF_DEVICES, {})):
        flat[pair[0]] = pad_physical_address(pair[1])

    global CEC_CLIENT
    CEC_CLIENT = pyCecClient(hass)
    exclude = config.get(CONF_EXCLUDE)

    def _start_cec(event):
        """Open CEC adapter."""
        # initialise libCEC and enter the main loop
        if CEC_CLIENT.InitLibCec():
            hass.services.register(DOMAIN, SERVICE_POWER_ON, CEC_CLIENT.ProcessCommandPowerOn)
            hass.services.register(DOMAIN, SERVICE_STANDBY, CEC_CLIENT.ProcessCommandStandby)
            hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE, CEC_CLIENT.ProcessCommandActiveSource)
            hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, CEC_CLIENT.ProcessCommandTx)
            hass.services.register(DOMAIN, SERVICE_SELF, CEC_CLIENT.ProcessCommandSelf)
            hass.services.register(DOMAIN, SERVICE_VOLUME, CEC_CLIENT.ProcessCommandVolume)
            for c in range(15):
                if exclude is not None and c in exclude:
                    continue
                # dev_type = CEC_TYPE_TO_COMPONENT[CEC_LOGICAL_TO_TYPE[c]]
                dev_type = 'switch'
                _LOGGER.info("Probing %d %d %s", c, CEC_LOGICAL_TO_TYPE[c], dev_type)
                if dev_type is None:
                    continue
                CEC_DEVICES[dev_type].append(c)
            for c in ['media_player', 'switch']:
                discovery.load_platform(hass, c, DOMAIN, {}, base_config)
            return True
        else:
            return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    return True


class CecDevice(Entity):
    """Representation of a HDMI CEC device entity."""

    deviceTypeNames = ["TV", "Recorder", "UNKNOWN", "Tuner", "Playback", "Audio"]

    def __init__(self, hass, cecClient, logical):
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
        _LOGGER.info("Initializing CEC device %s", self.name)
        self.cecClient = cecClient
        cecClient.RegisterCallback(self._update_callback)
        self.update()

    @asyncio.coroutine
    def async_update(self):
        if self.available:
            _LOGGER.info("Updating status for device %s", hex(self._logical_address)[2:])
            self._request_cec_power_status()
            self._request_cec_osd_name()
            self._request_cec_vendor()
            self._request_physical_address()
        else:
            _LOGGER.info("device not available. Not updating")

    def _request_physical_address(self):
        self.cecClient.ProcessCommandTx(
            type('call', (object,), {'data': {'dst': hex(self._logical_address)[2:], 'cmd': '83'}}))

    def _request_cec_vendor(self):
        self.cecClient.ProcessCommandTx(
            type('call', (object,), {'data': {'dst': hex(self._logical_address)[2:], 'cmd': '8C'}}))

    def _request_cec_osd_name(self):
        self.cecClient.ProcessCommandTx(
            type('call', (object,), {'data': {'dst': hex(self._logical_address)[2:], 'cmd': '46'}}))

    def _request_cec_power_status(self):
        self.cecClient.ProcessCommandTx(
            type('call', (object,), {'data': {'dst': hex(self._logical_address)[2:], 'cmd': '8F'}}))

    def turn_on(self):
        """Turn device on."""
        self.cecClient.SendCommandPowerOn(self._logical_address)
        self._state = STATE_ON
        self.schedule_update_ha_state()
        self._request_cec_power_status()

    def turn_off(self):
        """Turn device off."""
        self.cecClient.SendCommandStandby(self._logical_address)
        self._state = STATE_OFF
        self.schedule_update_ha_state()
        self._request_cec_power_status()

    def _update_callback(self, src, dst, response, cmd, cmdChain):
        if not (src == self._logical_address or src == 15):
            return
        _LOGGER.info("Got status for device %x -> %x, %s %x %s", src, dst, response, cmd, cmdChain)
        if cmd == 0x90:
            status = int(cmdChain[0], 16)
            _LOGGER.info("status: %s", status)
            if status == 0x00:
                self._state = STATE_ON
            elif status == 0x01:
                self._state = STATE_OFF
            else:
                self._state = STATE_UNKNOWN
            _LOGGER.info("state set to %s", self._state)
        elif cmd == 0x47:
            self._name = ''
            for c in cmdChain:
                self._name += chr(int(c, 16))
        elif cmd == 0x87:
            self._vendor_id = 0
            for i in cmdChain:
                self._vendor_id *= 0x100
                self._vendor_id += int(i, 16)
        elif cmd == 0x84:
            self._physical_address = "%d.%d.%d.%d" % (
                int(cmdChain[0][0], 16), int(cmdChain[0][1], 16), int(cmdChain[1][0], 16),
                int(cmdChain[1][1], 16))
            self._cec_type_id = int(cmdChain[2], 16)

        if self.entity_id is not None:
            self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self):
        return "%s%d" % (DOMAIN, self._logical_address)

    @property
    def friendly_name(self):
        """Return the name of the device."""
        n = self._name if self._name is not None else self.vendor_name if self.vendor_name is not None else None
        return "%s %d" % (deviceTypeNames[self._cec_type_id], self._logical_address) if n is None \
            else "%s %d (%s)" % (deviceTypeNames[self._cec_type_id], self._logical_address, n)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

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
        return deviceTypeNames[self._cec_type_id]

    @property
    def type_id(self):
        return self._cec_type_id

    @property
    def icon(self):
        return self._icon_by_type(self._cec_type_id) if self._icon is None else self._icon

    @property
    def hidden(self):
        return self._hidden or not self.available

    @property
    def available(self):
        return self.cecClient.lib.PollDevice(self._logical_address)

    def _icon_by_type(self, type):
        _LOGGER.info("Serving icon for type %d" % type)
        return \
            'mdi:television' if type == 0 else \
                'mdi:microphone' if type == 1 else \
                    'mdi:nest-thermostat' if type == 3 else \
                        'mdi:play' if type == 4 else \
                            'mdi:speaker' if type == 5 else \
                                'mdi:help'

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        if self.vendor_id is not None:
            state_attr['vendor_id'] = self.vendor_id
            state_attr['vendor_name'] = self.vendor_name
        if self.type_id is not None:
            state_attr['type_id'] = self.type_id
            state_attr['type'] = self.type
        if self.physical_address is not None:
            state_attr['physical_address'] = self.physical_address
        return state_attr


class pyCecClient:
    cecconfig = {}
    lib = {}
    hass = {}
    callbacks = []

    def DetectAdapter(self):
        """detect an adapter and return the com port path"""
        retval = None
        adapters = self.lib.DetectAdapters()
        for adapter in adapters:
            _LOGGER.info("found a CEC adapter:")
            _LOGGER.info("port:     " + adapter.strComName)
            _LOGGER.info("vendor:   " + hex(adapter.iVendorId))
            _LOGGER.info("product:  " + hex(adapter.iProductId))
            retval = adapter.strComName
        return retval

    def InitLibCec(self):
        """initialise libCEC"""
        self.lib = cec.ICECAdapter.Create(self.cecconfig)
        # print libCEC version and compilation information
        _LOGGER.info("libCEC version " + self.lib.VersionToString(
            self.cecconfig.serverVersion) + " loaded: " + self.lib.GetLibInfo())

        # search for adapters
        adapter = self.DetectAdapter()
        if adapter == None:
            _LOGGER.info("No adapters found")
            return False
        else:
            if self.lib.Open(adapter):
                self.lib.GetCurrentConfiguration(self.cecconfig)
                _LOGGER.info("connection opened")
                return True
            else:
                _LOGGER.info("failed to open a connection to the CEC adapter")
                return False

    def GetMyAddress(self):
        return self.cecconfig.logicalAddresses.primary

    def ProcessCommandSelf(self, call):
        """display the addresses controlled by libCEC"""
        addresses = self.lib.GetLogicalAddresses()
        result = "Addresses controlled by libCEC: "
        x = 0
        notFirst = False
        while x < 15:
            if addresses.IsSet(x):
                if notFirst:
                    result += ", "
                result += self.lib.LogicalAddressToString(x)
                if self.lib.IsActiveSource(x):
                    result += " (*)"
                notFirst = True
            x += 1
        _LOGGER.info(result)
        _LOGGER.info("%s", yaml.dump(result, indent=2))
        return result

    def ProcessCommandActiveSource(self, call):
        """send an active source message"""
        self.lib.SetActiveSource(int(call.data[ATTR_TYPE], 16))

    def SendCommandStandby(self, addr):
        """send a standby command"""
        _LOGGER.info("Standby device %s", addr)
        self.lib.StandbyDevices(cec.CECDEVICE_BROADCAST if addr is None else addr)

    def ProcessCommandStandby(self, call):
        """send a standby command"""
        self.SendCommandStandby(call.data)

    def SendCommandPowerOn(self, addr):
        _LOGGER.info("Power on device %s", addr)
        self.lib.PowerOnDevices(cec.CECDEVICE_BROADCAST if addr is None else addr)

    def ProcessCommandPowerOn(self, call):
        self.SendCommandPowerOn(call.data)

    def ProcessCommandVolume(self, call):
        for cmd, att in call.data:
            att = int(att)
            if att < 1: att = 1
            if cmd == CMD_UP:
                for _ in range(att): self.lib.VolumeUp(True)
                _LOGGER.info("Volume increased %d times", att)
            elif cmd == CMD_DOWN:
                for _ in range(att): self.lib.VolumeDown(True)
                _LOGGER.info("Volume deceased %d times", att)
            elif cmd == CMD_MUTE:
                self.lib.AudioMute()
                _LOGGER.info("Audio muted")
            elif cmd == CMD_UNMUTE:
                self.lib.AudioUnmute()
                _LOGGER.info("Audio unmuted")
            elif cmd == CMD_MUTE_TOGGLE:
                self.lib.AudioToggleMute()
                _LOGGER.info("Audio mute toggled")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    def ProcessCommandTx(self, call):
        """Send CEC command."""
        if call.data is list:
            data = call.data
        else:
            data = [call.data]
        _LOGGER.info("data %s", data)
        for d in data:
            if ATTR_RAW in d:
                command = d[ATTR_RAW]
            else:
                if ATTR_SRC in d:
                    src = d[ATTR_SRC]
                else:
                    src = str(self.GetMyAddress())
                    _LOGGER.info("src %s", src)
                if ATTR_DST in d:
                    dst = d[ATTR_DST]
                else:
                    dst = "f"
                if ATTR_CMD in d:
                    cmd = d[ATTR_CMD]
                else:
                    _LOGGER.error("Attribute 'cmd' is missing")
                    return False
                if ATTR_ATT in d:
                    att = ":%s" % d[ATTR_ATT]
                else:
                    att = ""
                command = "%s%s:%s%s" % (src, dst, cmd, att)
            _LOGGER.info("Sending %s", command)
            self.SendCommand(command)

    def SendCommand(self, data):
        """send a custom command to cec adapter"""
        cmd = self.lib.CommandFromString(data)
        _LOGGER.info("transmit " + data)
        if self.lib.Transmit(cmd):
            _LOGGER.info("command sent")
        else:
            _LOGGER.error("failed to send command")

    def ProcessCommandScan(self, call):
        """scan the bus and display devices that were found"""
        _LOGGER.info("requesting CEC bus information ...")
        strLog = "CEC bus information\n===================\n"
        addresses = self.lib.GetActiveDevices()
        x = 0
        while x < 15:
            if addresses.IsSet(x):
                vendorId = self.lib.GetDeviceVendorId(x)
                physicalAddress = self.lib.GetDevicePhysicalAddress(x)
                active = self.lib.IsActiveSource(x)
                cecVersion = self.lib.GetDeviceCecVersion(x)
                power = self.lib.GetDevicePowerStatus(x)
                osdName = self.lib.GetDeviceOSDName(x)
                strLog += "device #" + str(x) + ": " + self.lib.LogicalAddressToString(x) + "\n"
                strLog += "address:       " + str(physicalAddress) + "\n"
                strLog += "active source: " + str(active) + "\n"
                strLog += "vendor:        " + self.lib.VendorIdToString(vendorId) + "\n"
                strLog += "CEC version:   " + self.lib.CecVersionToString(cecVersion) + "\n"
                strLog += "OSD name:      " + osdName + "\n"
                strLog += "power status:  " + self.lib.PowerStatusToString(power) + "\n\n\n"
            x += 1
        _LOGGER.info(strLog)

    def RegisterCallback(self, callback):
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def LogCallback(self, level, time, message):
        """logging callback"""
        if level == cec.CEC_LOG_ERROR:
            levelstr = "ERROR:   "
            _LOGGER.error(levelstr + "[" + str(time) + "]     " + message)
        elif level == cec.CEC_LOG_WARNING:
            levelstr = "WARNING: "
            _LOGGER.warning(levelstr + "[" + str(time) + "]     " + message)
        elif level == cec.CEC_LOG_NOTICE:
            levelstr = "NOTICE:  "
            _LOGGER.info(levelstr + "[" + str(time) + "]     " + message)
        elif level == cec.CEC_LOG_TRAFFIC:
            levelstr = "TRAFFIC: "
            _LOGGER.info(levelstr + "[" + str(time) + "]     " + message)
        elif level == cec.CEC_LOG_DEBUG:
            levelstr = "DEBUG:   "
            _LOGGER.debug(levelstr + "[" + str(time) + "]     " + message)
        else:
            levelstr = "UNKNOWN:   "
            _LOGGER.error(levelstr + "[" + str(time) + "]     " + message)

        return 0

    def KeyPressCallback(self, key, duration):
        """key press callback"""
        _LOGGER.info("[key pressed] " + str(key))
        self.hass.bus.fire(EVENT_CEC_KEYPRESS_RECEIVED, {ATTR_KEY: key, ATTR_DURATION: duration})
        return 0

    def CommandCallback(self, command):
        """command received callback"""
        _LOGGER.info("[command receivedx] %s", command)
        dir = command[0:2]
        command = command[3:]
        cmdChain = command.split(':')
        src = cmdChain.pop(0)
        dst = int(src[1], 16)
        src = int(src[0], 16)
        cmd = int(cmdChain.pop(0), 16)
        _LOGGER.info("[command received1] " + command)
        if cmd == '00':
            response = True
            cmd = cmdChain.pop(0)
        else:
            response = False
        _LOGGER.info("[command received2] %s %s %s", src, dst, cmd)
        try:
            for c in self.callbacks:
                c(src, dst, response, cmd, cmdChain)
        except Exception as e:
            _LOGGER.error(e, exc_info=1)

        self.hass.bus.fire(EVENT_CEC_COMMAND_RECEIVED, {ATTR_COMMAND: command})
        return 0

    def __init__(self, hass):
        self.cecconfig = cec.libcec_configuration()
        self.cecconfig.strDeviceName = "pyLibCec"
        self.cecconfig.bActivateSource = 0
        self.cecconfig.bMonitorOnly = 0
        self.cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
        self.cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT
        self.hass = hass
        _LOGGER.debug("Setting callbacks...")
        self.cecconfig.SetLogCallback(self.LogCallback)
        self.cecconfig.SetKeyPressCallback(self.KeyPressCallback)
        self.cecconfig.SetCommandCallback(self.CommandCallback)
        _LOGGER.debug("callbacks set")
