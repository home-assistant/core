"""
CEC component.

Requires libcec + Python bindings.
"""

import logging
import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_START
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)
_CEC = None
DOMAIN = 'hdmi_cec'
SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_POWER_ON = 'power_on'
SERVICE_STANDBY = 'standby'
CONF_DEVICES = 'devices'
ATTR_DEVICE = 'device'
MAX_DEPTH = 4


# pylint: disable=unnecessary-lambda
DEVICE_SCHEMA = vol.Schema({
    vol.All(cv.positive_int): vol.Any(lambda devices: DEVICE_SCHEMA(devices),
                                      cv.string)
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


def setup(hass, config):
    """Setup CEC capability."""
    global _CEC

    # cec is only available if libcec is properly installed
    # and the Python bindings are accessible.
    try:
        import cec
    except ImportError:
        _LOGGER.error("libcec must be installed")
        return False

    # Parse configuration into a dict of device name
    # to physical address represented as a list of
    # four elements.
    flat = {}
    for pair in parse_mapping(config[DOMAIN].get(CONF_DEVICES, {})):
        flat[pair[0]] = pad_physical_address(pair[1])

    # Configure libcec.
    cfg = cec.libcec_configuration()
    cfg.strDeviceName = 'HASS'
    cfg.bActivateSource = 0
    cfg.bMonitorOnly = 1
    cfg.clientVersion = cec.LIBCEC_VERSION_CURRENT

    # Set up CEC adapter.
    _CEC = cec.ICECAdapter.Create(cfg)

    def _power_on(call):
        """Power on all devices."""
        _CEC.PowerOnDevices()

    def _standby(call):
        """Standby all devices."""
        _CEC.StandbyDevices()

    def _select_device(call):
        """Select the active device."""
        path = flat.get(call.data[ATTR_DEVICE])
        if not path:
            _LOGGER.error("Device not found: %s", call.data[ATTR_DEVICE])
        cmds = []
        for i in range(1, MAX_DEPTH - 1):
            addr = pad_physical_address(path[:i])
            cmds.append('1f:82:{}{}:{}{}'.format(*addr))
            cmds.append('1f:86:{}{}:{}{}'.format(*addr))
        for cmd in cmds:
            _CEC.Transmit(_CEC.CommandFromString(cmd))
        _LOGGER.info("Selected %s", call.data[ATTR_DEVICE])

    def _start_cec(event):
        """Open CEC adapter."""
        adapters = _CEC.DetectAdapters()
        if len(adapters) == 0:
            _LOGGER.error("No CEC adapter found")
            return

        if _CEC.Open(adapters[0].strComName):
            hass.services.register(DOMAIN, SERVICE_POWER_ON, _power_on)
            hass.services.register(DOMAIN, SERVICE_STANDBY, _standby)
            hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE,
                                   _select_device)
        else:
            _LOGGER.error("Failed to open adapter")

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    return True
