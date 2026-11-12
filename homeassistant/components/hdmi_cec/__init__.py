"""Support for HDMI CEC."""

import logging
import multiprocessing
from typing import Any

import probatio
from pycec.cec import CecAdapter
from pycec.network import HDMINetwork, PhysicalAddress
from pycec.tcp import TcpAdapter

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PLATFORM,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery, event
from homeassistant.helpers.typing import ConfigType

from .const import DATA_HDMI_CEC, DOMAIN, EVENT_HDMI_CEC_UNAVAILABLE
from .services import HdmiCecData, setup_services

_LOGGER = logging.getLogger(__name__)

DEFAULT_DISPLAY_NAME = "HA"
CONF_TYPES = "types"

CMD_UNMUTE = "unmute"
CMD_MUTE_TOGGLE = "toggle mute"

EVENT_CEC_COMMAND_RECEIVED = "cec_command_received"
EVENT_CEC_KEYPRESS_RECEIVED = "cec_keypress_received"

ATTR_KEY = "key"
ATTR_DUR = "dur"
ATTR_DIR = "dir"
ATTR_ABT = "abt"
ATTR_NEW = "new"

DEVICE_SCHEMA: probatio.Schema = probatio.Schema(
    {
        probatio.All(cv.positive_int): probatio.Any(
            # pylint: disable-next=unnecessary-lambda
            lambda devices: DEVICE_SCHEMA(devices),
            cv.string,
        )
    }
)

CONF_DISPLAY_NAME = "osd_name"

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Optional(CONF_DEVICES): probatio.Any(
                    DEVICE_SCHEMA,
                    probatio.Schema({probatio.All(cv.string): probatio.Any(cv.string)}),
                ),
                probatio.Optional(CONF_PLATFORM): probatio.Any(
                    SWITCH_DOMAIN, MEDIA_PLAYER_DOMAIN
                ),
                probatio.Optional(CONF_HOST): cv.string,
                probatio.Optional(CONF_DISPLAY_NAME): cv.string,
                probatio.Optional(CONF_TYPES, default={}): probatio.Schema(
                    {cv.entity_id: probatio.Any(MEDIA_PLAYER_DOMAIN, SWITCH_DOMAIN)}
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

WATCHDOG_INTERVAL = 120


def pad_physical_address(addr):
    """Right-pad a physical address."""
    return addr + [0] * (4 - len(addr))


def parse_mapping(mapping, parents=None):
    """Parse configuration device mapping."""
    if parents is None:
        parents = []
    for addr, val in mapping.items():
        if isinstance(addr, (str,)) and isinstance(val, (str,)):
            yield (addr, PhysicalAddress(val))
        else:
            cur = [*parents, addr]
            if isinstance(val, dict):
                yield from parse_mapping(val, cur)
            elif isinstance(val, str):
                yield (val, pad_physical_address(cur))


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the CEC capability."""

    hass.data[DOMAIN] = {}

    # Parse configuration into a dict of device name to physical address
    # represented as a list of four elements.
    device_aliases = {}
    devices = base_config[DOMAIN].get(CONF_DEVICES, {})
    _LOGGER.debug("Parsing config %s", devices)
    device_aliases.update(parse_mapping(devices))
    _LOGGER.debug("Parsed devices: %s", device_aliases)

    platform = base_config[DOMAIN].get(CONF_PLATFORM, SWITCH_DOMAIN)

    loop = (
        # Create own thread if more than 1 CPU
        hass.loop if multiprocessing.cpu_count() < 2 else None
    )
    host = base_config[DOMAIN].get(CONF_HOST)
    display_name = base_config[DOMAIN].get(CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    if host:
        adapter = TcpAdapter(host, name=display_name, activate_source=False)
    else:
        adapter = CecAdapter(name=display_name[:12], activate_source=False)
    hdmi_network = HDMINetwork(adapter, loop=loop)
    hass.data[DATA_HDMI_CEC] = HdmiCecData(hdmi_network, device_aliases)

    def _adapter_watchdog(now=None):
        _LOGGER.debug("Reached _adapter_watchdog")
        event.call_later(hass, WATCHDOG_INTERVAL, _adapter_watchdog_job)
        if not adapter.initialized:
            _LOGGER.warning("Adapter not initialized; Trying to restart")
            hass.bus.fire(EVENT_HDMI_CEC_UNAVAILABLE)
            adapter.init()

    _adapter_watchdog_job = HassJob(_adapter_watchdog, cancel_on_shutdown=True)

    @callback
    def _async_initialized_callback(*_: Any):
        """Add watchdog on initialization."""
        return event.async_call_later(hass, WATCHDOG_INTERVAL, _adapter_watchdog_job)

    hdmi_network.set_initialized_callback(_async_initialized_callback)

    def _new_device(device):
        """Handle new devices which are detected by HDMI network."""
        key = f"{DOMAIN}.{device.name}"
        hass.data[DOMAIN][key] = device
        ent_platform = base_config[DOMAIN][CONF_TYPES].get(key, platform)
        discovery.load_platform(
            hass,
            ent_platform,
            DOMAIN,
            discovered={ATTR_NEW: [key]},
            hass_config=base_config,
        )

    def _shutdown(call):
        hdmi_network.stop()

    def _start_cec(callback_event):
        """Start HDMI network to watch for devices."""
        hdmi_network.set_new_device_callback(_new_device)
        hdmi_network.start()

    setup_services(hass)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    return True
