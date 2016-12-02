"""
CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
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

global CEC_CLIENT

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
CONF_EXCLUDE = 'exclude'

MAX_DEPTH = 4

SERVICE_POWER_ON = 'power_on'
SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_STANDBY = 'standby'
SERVICE_SELF = 'self'
SERVICE_VOLUME = 'volume'

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

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICES): DEVICE_SCHEMA
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
            for logicalAddress in range(15):
                if exclude is None or logicalAddress in exclude:
                    continue
                dev_type = CEC_TYPE_TO_COMPONENT[CEC_LOGICAL_TO_TYPE[logicalAddress]]
                if dev_type is None:
                    continue
                CEC_DEVICES[dev_type].append(logicalAddress)
            for component in CEC_TYPE_TO_COMPONENT:
                _LOGGER.info("registering component %s", component)
                discovery.load_platform(hass, component, DOMAIN, {}, base_config)
            return True
        else:
            return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    return True


class CecDevice(Entity):
    """Representation of a HDMI CEC device entity."""

    deviceTypeNames = ["TV", "Recorder", "UNKNOWN", "Tuner", "Playback", "Audio"]

    def __init__(self, cecClient, logical=None, physical=None):
        """Initialize the device."""
        self.physicalAddress = physical
        self.logicalAddress = logical
        self.type = CEC_LOGICAL_TO_TYPE[logical]
        self.cecClient = cecClient
        cecClient.RegisterCallback(self._update_callback, src=logical)
        self.update()

    def async_update(self):
        self.cecClient.ProcessCommandTx({'dst': hex(self.logicalAddress)[2:], 'cmd': '8F'})

    def _update_callback(self, src, dst, response, cmd, cmdChain):
        if cmd == '90':
            status = cmdChain[0]
            if status == '00':
                self._state = STATE_ON
            elif status == '01':
                self._state = STATE_OFF
            else:
                self._state = STATE_UNKNOWN
            self.update()
            self.schedule_update_ha_state()

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.cecClient.ProcessCommandPowerOn()
        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.cecClient.ProcessCommandPowerOn()
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['CEC Device Id'] = self.logicalAddress
        return attr


def _commandHash(src, dst, cmd, response, ):
    if response is None:
        response = 0
    elif response:
        response = 1
    else:
        response = 2
    return response * 0x1000 + src * 0x100 + dst * 0x10 + cmd


class pyCecClient:
    cecconfig = {}
    lib = {}
    hass = {}
    callbacks = {}

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

    def ProcessCommandStandby(self, call):
        """send a standby command"""
        _LOGGER.info("Standby all devices ")
        self.lib.StandbyDevices(cec.CECDEVICE_BROADCAST)

    def ProcessCommandPowerOn(self, call):
        _LOGGER.info("Power on all devices ")
        self.lib.PowerOnDevices(cec.CECDEVICE_BROADCAST)

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
        activeSource = self.lib.GetActiveSource()
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

    def RegisterCallback(self, callback, src=15, dst=15, cmd=0, response=False):
        self.callbacks[_commandHash(src, dst, cmd, response)].append(callback)

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

    def CommandCallback(self, cmd):
        """command received callback"""
        _LOGGER.info("[command received] " + cmd)
        self.hass.bus.fire(EVENT_CEC_COMMAND_RECEIVED, {ATTR_COMMAND: cmd})

        cmdChain = cmd.split(':')
        src = cmdChain.pop(0)
        dst = src[1]
        src = src[0]
        cmd = cmdChain.pop(0)
        if cmd == '00':
            response = True
            cmd = cmdChain.pop(0)
        else:
            response = False

        commands = set()
        commands.union(self.callbacks.get(_commandHash(15, 15, 0, None)))
        commands.union(self.callbacks.get(_commandHash(15, 15, 0, response)))
        commands.union(self.callbacks.get(_commandHash(15, 15, cmd, None)))
        commands.union(self.callbacks.get(_commandHash(15, 15, cmd, response)))
        commands.union(self.callbacks.get(_commandHash(15, dst, 0, None)))
        commands.union(self.callbacks.get(_commandHash(15, dst, 0, response)))
        commands.union(self.callbacks.get(_commandHash(15, dst, cmd, None)))
        commands.union(self.callbacks.get(_commandHash(15, dst, cmd, response)))
        commands.union(self.callbacks.get(_commandHash(src, 15, 0, None)))
        commands.union(self.callbacks.get(_commandHash(src, 15, 0, response)))
        commands.union(self.callbacks.get(_commandHash(src, 15, cmd, None)))
        commands.union(self.callbacks.get(_commandHash(src, 15, cmd, response)))
        commands.union(self.callbacks.get(_commandHash(src, dst, 0, None)))
        commands.union(self.callbacks.get(_commandHash(src, dst, 0, response)))
        commands.union(self.callbacks.get(_commandHash(src, dst, cmd, None)))
        commands.union(self.callbacks.get(_commandHash(src, dst, cmd, response)))
        for c in commands:
            c(src, dst, response, cmd, cmdChain)

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
