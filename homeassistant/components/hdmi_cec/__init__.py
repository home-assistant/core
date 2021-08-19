"""Support for HDMI CEC."""
from __future__ import annotations

from functools import partial, reduce
import logging
import multiprocessing

from pycec.cec import CecAdapter
from pycec.commands import CecCommand, KeyPressCommand, KeyReleaseCommand
from pycec.const import (
    ADDR_AUDIOSYSTEM,
    ADDR_BROADCAST,
    ADDR_UNREGISTERED,
    KEY_MUTE_OFF,
    KEY_MUTE_ON,
    KEY_MUTE_TOGGLE,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
    POWER_OFF,
    POWER_ON,
    STATUS_PLAY,
    STATUS_STILL,
    STATUS_STOP,
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
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery, event
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

DOMAIN = "hdmi_cec"

_LOGGER = logging.getLogger(__name__)

DEFAULT_DISPLAY_NAME = "HA"
CONF_TYPES = "types"

ICON_UNKNOWN = "mdi:help"
ICON_AUDIO = "mdi:speaker"
ICON_PLAYER = "mdi:play"
ICON_TUNER = "mdi:radio"
ICON_RECORDER = "mdi:microphone"
ICON_TV = "mdi:television"
ICONS_BY_TYPE = {
    0: ICON_TV,
    1: ICON_RECORDER,
    3: ICON_TUNER,
    4: ICON_PLAYER,
    5: ICON_AUDIO,
}

CMD_UP = "up"
CMD_DOWN = "down"
CMD_MUTE = "mute"
CMD_UNMUTE = "unmute"
CMD_MUTE_TOGGLE = "toggle mute"
CMD_PRESS = "press"
CMD_RELEASE = "release"

EVENT_CEC_COMMAND_RECEIVED = "cec_command_received"
EVENT_CEC_KEYPRESS_RECEIVED = "cec_keypress_received"

ATTR_PHYSICAL_ADDRESS = "physical_address"
ATTR_TYPE_ID = "type_id"
ATTR_VENDOR_NAME = "vendor_name"
ATTR_VENDOR_ID = "vendor_id"
ATTR_DEVICE = "device"
ATTR_TYPE = "type"
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

# pylint: disable=unnecessary-lambda
DEVICE_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.All(cv.positive_int): vol.Any(
            lambda devices: DEVICE_SCHEMA(devices), cv.string
        )
    }
)

CONF_DISPLAY_NAME = "osd_name"

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
                vol.Optional(CONF_TYPES, default={}): vol.Schema(
                    {cv.entity_id: vol.Any(MEDIA_PLAYER, SWITCH)}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

WATCHDOG_INTERVAL = 120
EVENT_HDMI_CEC_UNAVAILABLE = "hdmi_cec_unavailable"


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
            cur = parents + [addr]
            if isinstance(val, dict):
                yield from parse_mapping(val, cur)
            elif isinstance(val, str):
                yield (val, pad_physical_address(cur))


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:  # noqa: C901
    """Set up the CEC capability."""

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
        hass.loop
        if multiprocessing.cpu_count() < 2
        else None
    )
    host = base_config[DOMAIN].get(CONF_HOST)
    display_name = base_config[DOMAIN].get(CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    if host:
        adapter = TcpAdapter(host, name=display_name, activate_source=False)
    else:
        adapter = CecAdapter(name=display_name[:12], activate_source=False)
    hdmi_network = HDMINetwork(adapter, loop=loop)

    def _adapter_watchdog(now=None):
        _LOGGER.debug("Reached _adapter_watchdog")
        event.async_call_later(hass, WATCHDOG_INTERVAL, _adapter_watchdog)
        if not adapter.initialized:
            _LOGGER.info("Adapter not initialized; Trying to restart")
            hass.bus.fire(EVENT_HDMI_CEC_UNAVAILABLE)
            adapter.init()

    hdmi_network.set_initialized_callback(
        partial(event.async_call_later, hass, WATCHDOG_INTERVAL, _adapter_watchdog)
    )

    def _volume(call):
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
                _LOGGER.info("Audio muted")
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
            for _ in range(0, att):
                hdmi_network.send_command(KeyPressCommand(cmd, dst=ADDR_AUDIOSYSTEM))
                hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))

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
                    att = reduce(lambda x, y: f"{x}:{y:x}", data[ATTR_ATT])
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
        _LOGGER.info("Selected %s (%s)", call.data[ATTR_DEVICE], addr)

    def _update(call):
        """
        Update if device update is needed.

        Called by service, requests CEC network to update data.
        """
        hdmi_network.scan()

    def _new_device(device):
        """Handle new devices which are detected by HDMI network."""
        key = f"{DOMAIN}.{device.name}"
        hass.data[key] = device
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


class CecEntity(Entity):
    """Representation of a HDMI CEC device entity."""

    _attr_should_poll = False

    def __init__(self, device, logical) -> None:
        """Initialize the device."""
        self._device = device
        self._state: str | None = None
        self._logical_address = logical
        self.entity_id = "%s.%d" % (DOMAIN, self._logical_address)
        self._set_attr_name()
        if self._device.type in ICONS_BY_TYPE:
            self._attr_icon = ICONS_BY_TYPE[self._device.type]
        else:
            self._attr_icon = ICON_UNKNOWN

    def _set_attr_name(self):
        """Set name."""
        if (
            self._device.osd_name is not None
            and self.vendor_name is not None
            and self.vendor_name != "Unknown"
        ):
            self._attr_name = f"{self.vendor_name} {self._device.osd_name}"
        elif self._device.osd_name is None:
            self._attr_name = f"{self._device.type_name} {self._logical_address}"
        else:
            self._attr_name = f"{self._device.type_name} {self._logical_address} ({self._device.osd_name})"

    def _hdmi_cec_unavailable(self, callback_event):
        # Change state to unavailable. Without this, entity would remain in
        # its last state, since the state changes are pushed.
        self._state = STATE_UNAVAILABLE
        self.schedule_update_ha_state(False)

    def update(self):
        """Update device status."""
        device = self._device
        if device.power_status in [POWER_OFF, 3]:
            self._state = STATE_OFF
        elif device.status == STATUS_PLAY:
            self._state = STATE_PLAYING
        elif device.status == STATUS_STOP:
            self._state = STATE_IDLE
        elif device.status == STATUS_STILL:
            self._state = STATE_PAUSED
        elif device.power_status in [POWER_ON, 4]:
            self._state = STATE_ON
        else:
            _LOGGER.warning("Unknown state: %d", device.power_status)

    async def async_added_to_hass(self):
        """Register HDMI callbacks after initialization."""
        self._device.set_update_callback(self._update)
        self.hass.bus.async_listen(
            EVENT_HDMI_CEC_UNAVAILABLE, self._hdmi_cec_unavailable
        )

    def _update(self, device=None):
        """Device status changed, schedule an update."""
        self.schedule_update_ha_state(True)

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
    def extra_state_attributes(self):
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
