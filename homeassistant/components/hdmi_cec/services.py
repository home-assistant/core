"""Services for the HDMI CEC integration."""

from dataclasses import dataclass
from functools import reduce
import logging

import probatio
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
)
from pycec.network import HDMINetwork, PhysicalAddress

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DATA_HDMI_CEC, DOMAIN

_LOGGER = logging.getLogger(__name__)

CMD_UP = "up"
CMD_DOWN = "down"
CMD_MUTE = "mute"
CMD_PRESS = "press"
CMD_RELEASE = "release"

ATTR_DEVICE = "device"
ATTR_SRC = "src"
ATTR_DST = "dst"
ATTR_CMD = "cmd"
ATTR_ATT = "att"
ATTR_RAW = "raw"
ATTR_ON = "on"
ATTR_OFF = "off"
ATTR_TOGGLE = "toggle"

_VOL_HEX = probatio.Any(probatio.Coerce(int), lambda x: int(x, 16))

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SEND_COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_CMD): _VOL_HEX,
        probatio.Optional(ATTR_SRC): _VOL_HEX,
        probatio.Optional(ATTR_DST): _VOL_HEX,
        probatio.Optional(ATTR_ATT): _VOL_HEX,
        probatio.Optional(ATTR_RAW): probatio.Coerce(str),
    },
    extra=probatio.PREVENT_EXTRA,
)

SERVICE_VOLUME = "volume"
SERVICE_VOLUME_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CMD_UP): probatio.Any(
            CMD_PRESS, CMD_RELEASE, probatio.Coerce(int)
        ),
        probatio.Optional(CMD_DOWN): probatio.Any(
            CMD_PRESS, CMD_RELEASE, probatio.Coerce(int)
        ),
        probatio.Optional(CMD_MUTE): probatio.Any(ATTR_ON, ATTR_OFF, ATTR_TOGGLE),
    },
    extra=probatio.PREVENT_EXTRA,
)

SERVICE_UPDATE_DEVICES = "update"
SERVICE_UPDATE_DEVICES_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.Schema({})}, extra=probatio.PREVENT_EXTRA
)

SERVICE_SELECT_DEVICE = "select_device"

SERVICE_POWER_ON = "power_on"
SERVICE_STANDBY = "standby"


@dataclass(frozen=True, slots=True)
class HdmiCecData:
    """HDMI CEC network and configured device aliases."""

    hdmi_network: HDMINetwork
    device_aliases: dict[str, PhysicalAddress | list[int]]


def _volume(call: ServiceCall) -> None:
    """Increase/decrease volume and mute/unmute system."""
    hdmi_network = call.hass.data[DATA_HDMI_CEC].hdmi_network
    mute_key_mapping = {
        ATTR_TOGGLE: KEY_MUTE_TOGGLE,
        ATTR_ON: KEY_MUTE_ON,
        ATTR_OFF: KEY_MUTE_OFF,
    }
    for cmd, att in call.data.items():
        if cmd == CMD_UP:
            _process_volume(hdmi_network, KEY_VOLUME_UP, att)
        elif cmd == CMD_DOWN:
            _process_volume(hdmi_network, KEY_VOLUME_DOWN, att)
        elif cmd == CMD_MUTE:
            hdmi_network.send_command(
                KeyPressCommand(mute_key_mapping[att], dst=ADDR_AUDIOSYSTEM)
            )
            hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
            _LOGGER.debug("Audio muted")
        else:
            _LOGGER.warning("Unknown command %s", cmd)


def _process_volume(hdmi_network: HDMINetwork, cmd, att):
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
    call.hass.data[DATA_HDMI_CEC].hdmi_network.send_command(command)


def _standby(call: ServiceCall) -> None:
    call.hass.data[DATA_HDMI_CEC].hdmi_network.standby()


def _power_on(call: ServiceCall) -> None:
    call.hass.data[DATA_HDMI_CEC].hdmi_network.power_on()


def _select_device(call: ServiceCall) -> None:
    """Select the active device."""
    data = call.hass.data[DATA_HDMI_CEC]
    if not (addr := call.data[ATTR_DEVICE]):
        _LOGGER.error("Device not found: %s", call.data[ATTR_DEVICE])
        return
    if addr in data.device_aliases:
        addr = data.device_aliases[addr]
    else:
        entity = call.hass.states.get(addr)
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
    data.hdmi_network.active_source(addr)
    _LOGGER.debug("Selected %s (%s)", call.data[ATTR_DEVICE], addr)


def _update(call: ServiceCall) -> None:
    """Update if device update is needed.

    Called by service, requests CEC network to update data.
    """
    call.hass.data[DATA_HDMI_CEC].hdmi_network.scan()


def setup_services(hass: HomeAssistant) -> None:
    """Register the HDMI CEC services."""
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
