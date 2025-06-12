"""Support for HDMI CEC."""

from __future__ import annotations

from functools import reduce
import logging
import multiprocessing
from typing import Any

from pycec.cec import CecAdapter
from pycec.commands import CecCommand, KeyPressCommand, KeyReleaseCommand
from pycec.const import (
    ADDR_AUDIOSYSTEM,
    ADDR_BROADCAST,
    ADDR_FREEUSE,
    ADDR_PLAYBACKDEVICE1,
    ADDR_PLAYBACKDEVICE2,
    ADDR_PLAYBACKDEVICE3,
    ADDR_RECORDINGDEVICE1,
    ADDR_RECORDINGDEVICE2,
    ADDR_RECORDINGDEVICE3,
    ADDR_RESERVED1,
    ADDR_RESERVED2,
    ADDR_TUNER1,
    ADDR_TUNER2,
    ADDR_TUNER3,
    ADDR_TUNER4,
    ADDR_TV,
    ADDR_UNKNOWN,
    ADDR_UNREGISTERED,
    KEY_MUTE_OFF,
    KEY_MUTE_ON,
    KEY_MUTE_TOGGLE,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
)
from pycec.network import HDMINetwork, PhysicalAddress
from pycec.tcp import TcpAdapter
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PLATFORM,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HassJob, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, discovery, event
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_HDMI_CEC_UNAVAILABLE

_LOGGER = logging.getLogger(__name__)

DEFAULT_DISPLAY_NAME = "HA"
CONF_TYPES = "types"

CMD_UP = "up"
CMD_DOWN = "down"
CMD_MUTE = "mute"
CMD_UNMUTE = "unmute"
CMD_MUTE_TOGGLE = "toggle mute"
CMD_PRESS = "press"
CMD_RELEASE = "release"

EVENT_CEC_COMMAND_RECEIVED = "cec_command_received"
EVENT_CEC_KEYPRESS_RECEIVED = "cec_keypress_received"

ATTR_DEVICE = "device"
ATTR_KEY = "key"
ATTR_DUR = "dur"
ATTR_SRC = "src"
ATTR_DST = "dst"
ATTR_CMD = "cmd"
ATTR_ATT = "att"
ATTR_RAW = "raw"
ATTR_DIR = "dir"
ATTR_ABT = "abt"
ATTR_NEW = "new"
ATTR_ON = "on"
ATTR_OFF = "off"
ATTR_TOGGLE = "toggle"

_VOL_HEX = vol.Any(vol.Coerce(int), lambda x: int(x, 16))

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CMD): _VOL_HEX,
        vol.Optional(ATTR_SRC): _VOL_HEX,
        vol.Optional(ATTR_DST): _VOL_HEX,
        vol.Optional(ATTR_ATT): _VOL_HEX,
        vol.Optional(ATTR_RAW): vol.Coerce(str),
    },
    extra=vol.PREVENT_EXTRA,
)

SERVICE_VOLUME = "volume"
SERVICE_VOLUME_SCHEMA = vol.Schema(
    {
        vol.Optional(CMD_UP): vol.Any(CMD_PRESS, CMD_RELEASE, vol.Coerce(int)),
        vol.Optional(CMD_DOWN): vol.Any(CMD_PRESS, CMD_RELEASE, vol.Coerce(int)),
        vol.Optional(CMD_MUTE): vol.Any(ATTR_ON, ATTR_OFF, ATTR_TOGGLE),
    },
    extra=vol.PREVENT_EXTRA,
)

SERVICE_UPDATE_DEVICES = "update"
SERVICE_UPDATE_DEVICES_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({})}, extra=vol.PREVENT_EXTRA
)

SERVICE_SELECT_DEVICE = "select_device"

SERVICE_POWER_ON = "power_on"
SERVICE_STANDBY = "standby"

DEVICE_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.All(cv.positive_int): vol.Any(
            # pylint: disable-next=unnecessary-lambda
            lambda devices: DEVICE_SCHEMA(devices),
            cv.string,
        )
    }
)

CONF_DISPLAY_NAME = "osd_name"
CONF_DEVICE_TYPE = "device_type"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICES): vol.Any(
                    DEVICE_SCHEMA, vol.Schema({vol.All(cv.string): vol.Any(cv.string)})
                ),
                vol.Optional(CONF_PLATFORM): vol.Any(SWITCH, MEDIA_PLAYER),
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_DISPLAY_NAME): cv.string,
                vol.Optional(CONF_DEVICE_TYPE): vol.Any(ADDR_AUDIOSYSTEM, ADDR_BROADCAST, ADDR_FREEUSE, ADDR_PLAYBACKDEVICE1, ADDR_PLAYBACKDEVICE2, ADDR_PLAYBACKDEVICE3, ADDR_RECORDINGDEVICE1, ADDR_RECORDINGDEVICE2, ADDR_RECORDINGDEVICE3, ADDR_RESERVED1, ADDR_RESERVED2, ADDR_TUNER1, ADDR_TUNER2, ADDR_TUNER3, ADDR_TUNER4, ADDR_TV, ADDR_UNKNOWN, ADDR_UNREGISTERED),
                vol.Optional(CONF_TYPES, default={}): vol.Schema(
                    {cv.entity_id: vol.Any(MEDIA_PLAYER, SWITCH)}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
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


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:  # noqa: C901
    """Set up the CEC capability."""

    hass.data[DOMAIN] = {}

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
        hass.loop if multiprocessing.cpu_count() < 2 else None
    )
    host = base_config[DOMAIN].get(CONF_HOST)
    display_name = base_config[DOMAIN].get(CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    device_type = base_config[DOMAIN].get(CONF_DEVICE_TYPE, ADDR_RECORDINGDEVICE1)
    if host:
        adapter = TcpAdapter(host, name=display_name, activate_source=False)
    else:
        adapter = CecAdapter(name=display_name[:12], activate_source=False, device_type=device_type)
    hdmi_network = HDMINetwork(adapter, loop=loop)

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

    @callback
    def handle_cec_command(command: CecCommand):
        """Unified handler for CEC commands: GIVE_AUDIO_STATUS and keypress events."""
        _LOGGER.debug("Received CEC command: opcode=0x%02X from src=%d", command.cmd, command.src)

        if command.cmd == 0x71:  # GIVE_AUDIO_STATUS
            _LOGGER.warning("Received GIVE_AUDIO_STATUS from %d", command.src)

            # Broadcast request on Home Assistant bus
            hass.bus.fire("cec_audio_status_requested", {
                "source": command.src,
            })

            _LOGGER.debug("Fired cec_audio_status_requested event from source %d", command.src)

        elif command.cmd == 0x44:  # User Control Pressed / Keypress
            if command.att and len(command.att) >= 1:
                key_code = command.att[0]
            else:
                key_code = None

            _LOGGER.warning("Received key press from %d: key code = %s", command.src, key_code)

            # Fire Home Assistant event with key press details
            hass.bus.fire("cec_keypress_received", {
                "source": command.src,
                "key_code": key_code,
            })

            _LOGGER.debug("Fired cec_keypress_received: source=%d key_code=%s", command.src, key_code)

        else:
            _LOGGER.debug("Unhandled CEC command opcode: 0x%02X", command.cmd)

    # Register the callback
    hdmi_network.set_command_callback(handle_cec_command)

    def send_audio_status_event(event):
        """Handle HA event to send REPORT_AUDIO_STATUS CEC command."""
        data = event.data
        level = int(data.get("level", 50))  # Default to 50 if not specified
        muted = bool(data.get("muted", False))
        destination = int(data.get("destination", 0))

        # Compose the status byte (mute bit in MSB)
        status_byte = level | (0x80 if muted else 0x00)

        cmd = CecCommand(
            src=adapter.get_logical_address(),
            dst=destination,
            cmd=0x7A,
            att=[status_byte]
        )

        _LOGGER.info(
            "Sending REPORT_AUDIO_STATUS to %d: volume=%d, muted=%s (0x%02X)",
            destination, level, muted, status_byte
        )

        hdmi_network.send_command(cmd)

    hass.bus.listen("cec_send_audio_status", send_audio_status_event)

    def _volume(call: ServiceCall) -> None:
        """Increase/decrease volume and mute/unmute system."""
        mute_key_mapping = {
            ATTR_TOGGLE: KEY_MUTE_TOGGLE,
            ATTR_ON: KEY_MUTE_ON,
            ATTR_OFF: KEY_MUTE_OFF,
        }
        for cmd, att in call.data.items():
            if cmd == CMD_UP:
                _process_volume(KEY_VOLUME_UP, att)
            elif cmd == CMD_DOWN:
                _process_volume(KEY_VOLUME_DOWN, att)
            elif cmd == CMD_MUTE:
                hdmi_network.send_command(
                    KeyPressCommand(mute_key_mapping[att], dst=ADDR_AUDIOSYSTEM)
                )
                hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
                _LOGGER.debug("Audio muted")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    def _process_volume(cmd, att):
        if isinstance(att, (str,)):
            att = att.strip()
        if att == CMD_PRESS:
            hdmi_network.send_command(KeyPressCommand(cmd, dst=ADDR_AUDIOSYSTEM))
        elif att == CMD_RELEASE:
            hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
        else:
            att = 1 if att == "" else int(att)
            for _ in range(att):
                hdmi_network.send_command(KeyPressCommand(cmd, dst=ADDR_AUDIOSYSTEM))
                hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))

    def _tx(call: ServiceCall) -> None:
        """Send CEC command."""
        data = call.data
        if ATTR_RAW in data:
            command = CecCommand(data[ATTR_RAW])
        else:
            src = data.get(ATTR_SRC, ADDR_UNREGISTERED)
            dst = data.get(ATTR_DST, ADDR_BROADCAST)
            if ATTR_CMD in data:
                cmd = data[ATTR_CMD]
            else:
                _LOGGER.error("Attribute 'cmd' is missing")
                return
            if ATTR_ATT in data:
                if isinstance(data[ATTR_ATT], (list,)):
                    att = data[ATTR_ATT]
                else:
                    att = reduce(lambda x, y: f"{x}:{y:x}", data[ATTR_ATT])
            else:
                att = ""
            command = CecCommand(cmd, dst, src, att)
        hdmi_network.send_command(command)

    def _standby(call: ServiceCall) -> None:
        hdmi_network.standby()

    def _power_on(call: ServiceCall) -> None:
        hdmi_network.power_on()

    def _select_device(call: ServiceCall) -> None:
        """Select the active device."""
        if not (addr := call.data[ATTR_DEVICE]):
            _LOGGER.error("Device not found: %s", call.data[ATTR_DEVICE])
            return
        if addr in device_aliases:
            addr = device_aliases[addr]
        else:
            entity = hass.states.get(addr)
            _LOGGER.debug("Selecting entity %s", entity)
            if entity is not None:
                addr = entity.attributes["physical_address"]
                _LOGGER.debug("Address acquired: %s", addr)
                if addr is None:
                    _LOGGER.error(
                        "Device %s has not physical address", call.data[ATTR_DEVICE]
                    )
                    return
        if not isinstance(addr, (PhysicalAddress,)):
            addr = PhysicalAddress(addr)
        hdmi_network.active_source(addr)
        _LOGGER.debug("Selected %s (%s)", call.data[ATTR_DEVICE], addr)

    def _update(call: ServiceCall) -> None:
        """Update if device update is needed.

        Called by service, requests CEC network to update data.
        """
        hdmi_network.scan()

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
        """Register services and start HDMI network to watch for devices."""
        hass.services.register(
            DOMAIN, SERVICE_SEND_COMMAND, _tx, SERVICE_SEND_COMMAND_SCHEMA
        )
        hass.services.register(
            DOMAIN, SERVICE_VOLUME, _volume, schema=SERVICE_VOLUME_SCHEMA
        )
        hass.services.register(
            DOMAIN,
            SERVICE_UPDATE_DEVICES,
            _update,
            schema=SERVICE_UPDATE_DEVICES_SCHEMA,
        )
        hass.services.register(DOMAIN, SERVICE_POWER_ON, _power_on)
        hass.services.register(DOMAIN, SERVICE_STANDBY, _standby)
        hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE, _select_device)

        hdmi_network.set_new_device_callback(_new_device)
        hdmi_network.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    return True
