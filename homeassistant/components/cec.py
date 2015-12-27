import re
import logging
import threading
from concurrent.futures import thread

import homeassistant
from homeassistant import bootstrap
from homeassistant.const import EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED

DOMAIN = "cec"
#REQUIREMENTS = ['cec']
DISCOVER_OPTION = 'cec.option'

SERVICE_CEC_SET_STREAM_PATH = 'set_stream_path'

EVENT_CEC_DEVICE_CHANGED = 'cec_device_changed'

ATTR_CEC_LOGICAL_ADDRESS = 'logical_address'
ATTR_CEC_PHYSICAL_ADDRESS = 'physical_address'

_LOGGER = logging.getLogger(__name__)

PHYSICAL_ADRESS_REGEX = re.compile('([\dA-F])\.([\dA-F]).([\dA-F]).([\dA-F])')
CEC = None
DEVICES = {}


def physical_address_to_string(physical_address):
    return '.'.join(('%X' % (physical_address)))

class CecDevice(object):
    def __init__(self, logical_address):
        self.set_logical_address(logical_address)

    def __eq__(self, other):
        return isinstance(other, CecDevice) and \
               self.logical_address == other.logical_address and \
               self.vendor == other.vendor and \
               self.physical_address == other.physical_address and \
               self.active == other.active and \
               self.power == other.power and \
               self.osd == other.osd and \
               self.cec_version == other.cec_version

    def __str__(self):
        return "Device(logical=%s (%s); physical=%s; vendor=%s; osd=%s; cec_version=%s power=%s; active=%s)" % (
            self.logical_address, self.logical_address_string, self.physical_address, self.vendor, self.osd,
            self.cec_version, self.power, self.active
        )

    def set_logical_address(self, logical_address):
        self.logical_address = logical_address
        self._update_from_logical_address(logical_address)

    def _update_from_logical_address(self, logical_address):
        self.logical_address_string = CEC.LogicalAddressToString(self.logical_address)
        self.vendor = CEC.VendorIdToString(CEC.GetDeviceVendorId(logical_address))
        self.physical_address = physical_address_to_string(CEC.GetDevicePhysicalAddress(logical_address))
        self.active = CEC.IsActiveSource(logical_address)
        self.power = CEC.PowerStatusToString(CEC.GetDevicePowerStatus(logical_address))
        self.osd = CEC.GetDeviceOSDName(logical_address)
        self.cec_version = CEC.CecVersionToString(CEC.GetDeviceCecVersion(logical_address))


def set_stream_path(service):
    if CEC is None:
        return False

    dat = service.data

    if ATTR_CEC_PHYSICAL_ADDRESS not in dat:
        return

    physical_address = dat[ATTR_CEC_PHYSICAL_ADDRESS]
    print(type(physical_address), physical_address)

    # CEC.SetStreamPath(physical_address) results in the following error:
    # only the TV is allowed to send CEC_OPCODE_SET_STREAM_PATH
    # Technically, this is correct.. But this is the only possibility I found to
    # switch devices

    match = PHYSICAL_ADRESS_REGEX.match(physical_address)
    if not match:
        return

    a, b, c, d = match.groups()
    # From: Reserved (E)
    # To: Broadcast
    # Message: Routing Control - Set Stream Path
    CEC.Transmit(CEC.CommandFromString("EF:86:" + a + b + ":" + c + d))

def setup(hass, config):
    """
    Setup HDMI-CEC.
    Will automatically load components to support devices found on the network.
    """
    global CEC
    import cec

    map_log_level = {
        cec.CEC_LOG_ERROR: logging.ERROR,
        cec.CEC_LOG_WARNING: logging.WARNING,
        cec.CEC_LOG_NOTICE: logging.INFO,
        cec.CEC_LOG_TRAFFIC: logging.DEBUG,
        cec.CEC_LOG_DEBUG: logging.DEBUG
    }

    def update_devices(now):
        _LOGGER.info('\n\n\nUpdating CEC devices...')
        addresses = CEC.GetActiveDevices()
        for x in range(15):
            old_dev = DEVICES.get(x)
            new_dev = CecDevice(x) if addresses.IsSet(x) else None

            if old_dev != new_dev:
                if new_dev is not None:
                    DEVICES[x] = new_dev
                else:
                    DEVICES.pop(x, None)
                _LOGGER.info('CEC device %s changed:' % x)
                _LOGGER.info('old[%s]: %s' % (x, old_dev))
                _LOGGER.info('new[%s]: %s' % (x, new_dev))
                hass.bus.fire(EVENT_CEC_DEVICE_CHANGED, {ATTR_CEC_LOGICAL_ADDRESS: x})

    def log_callback(level, time, message):
        level = map_log_level.get(level, logging.WARNING)
        _LOGGER.log(level, '[%s] %s' % (str(time), message))

    cecconfig = cec.libcec_configuration()
    cecconfig.strDeviceName = 'homeassistant'

    # do not make it the active source on the bus when loading the component
    cecconfig.bActivateSource = 0

    #cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
    cecconfig.bMonitorOnly = 1
    cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT

    #cecconfig.SetLogCallback(log_callback)
    #cecconfig.SetCommandCallback(received_command)

    CEC = cec.ICECAdapter.Create(cecconfig)

    _LOGGER.info('libCEC version ' + CEC.VersionToString(cecconfig.serverVersion) + ' loaded: ' + CEC.GetLibInfo())

    adapters = CEC.DetectAdapters()

    if len(adapters) == 0:
        _LOGGER.info('No compatible HDMI-CEC adapter found!')
        return

    if len(adapters) > 1:
        _LOGGER.warning('More than one HDMI-CEC adapter found! Using first one!')

    adapter = adapters[0]

    _LOGGER.info('Using adapter: ' + adapter.strComName)

    if not CEC.Open(adapter.strComName):
        _LOGGER.error('failed to open a connection to the CEC adapter')
        return

    # Fire every 5 seconds
    homeassistant.helpers.event.track_time_change(hass, update_devices, second=range(0, 60, 5))

    # Ensure component is loaded
    bootstrap.setup_component(hass, 'option', config)

    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_OPTION,
        ATTR_DISCOVERED: {}
    })

    hass.services.register(DOMAIN, SERVICE_CEC_SET_STREAM_PATH, set_stream_path)

    return True
