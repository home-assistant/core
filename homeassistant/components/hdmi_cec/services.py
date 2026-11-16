"""Services for the HDMI CEC integration."""

from dataclasses import dataclass
from enum import StrEnum
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

CMD_PRESS = "press"
CMD_RELEASE = "release"

MUTE_ON = "on"
MUTE_OFF = "off"
MUTE_TOGGLE = "toggle"


class HdmiCecService(StrEnum):
    """Store keys for HDMI CEC services."""

    POWER_ON = "power_on"
    SELECT_DEVICE = "select_device"
    SEND_COMMAND = "send_command"
    STANDBY = "standby"
    UPDATE = "update"
    VOLUME = "volume"


class HdmiCecServiceArgument(StrEnum):
    """Store keys for HDMI CEC service arguments."""

    DEVICE = "device"
    ATT = "att"
    CMD = "cmd"
    DST = "dst"
    RAW = "raw"
    SRC = "src"
    DOWN = "down"
    MUTE = "mute"
    UP = "up"


_VOL_HEX = probatio.Any(probatio.Coerce(int), lambda x: int(x, 16))

SERVICE_SEND_COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Optional(HdmiCecServiceArgument.CMD): _VOL_HEX,
        probatio.Optional(HdmiCecServiceArgument.SRC): _VOL_HEX,
        probatio.Optional(HdmiCecServiceArgument.DST): _VOL_HEX,
        probatio.Optional(HdmiCecServiceArgument.ATT): _VOL_HEX,
        probatio.Optional(HdmiCecServiceArgument.RAW): probatio.Coerce(str),
    },
    extra=probatio.PREVENT_EXTRA,
)

SERVICE_VOLUME_SCHEMA = probatio.Schema(
    {
        probatio.Optional(HdmiCecServiceArgument.UP): probatio.Any(
            CMD_PRESS, CMD_RELEASE, probatio.Coerce(int)
        ),
        probatio.Optional(HdmiCecServiceArgument.DOWN): probatio.Any(
            CMD_PRESS, CMD_RELEASE, probatio.Coerce(int)
        ),
        probatio.Optional(HdmiCecServiceArgument.MUTE): probatio.Any(
            MUTE_ON, MUTE_OFF, MUTE_TOGGLE
        ),
    },
    extra=probatio.PREVENT_EXTRA,
)

SERVICE_UPDATE_DEVICES_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.Schema({})}, extra=probatio.PREVENT_EXTRA
)


@dataclass(frozen=True, slots=True)
class HdmiCecData:
    """HDMI CEC network and configured device aliases."""

    hdmi_network: HDMINetwork
    device_aliases: dict[str, PhysicalAddress | list[int]]


def _volume(call: ServiceCall) -> None:
    """Increase/decrease volume and mute/unmute system."""
    hdmi_network = call.hass.data[DATA_HDMI_CEC].hdmi_network
    mute_key_mapping = {
        MUTE_TOGGLE: KEY_MUTE_TOGGLE,
        MUTE_ON: KEY_MUTE_ON,
        MUTE_OFF: KEY_MUTE_OFF,
    }
    for cmd, att in call.data.items():
        if cmd == HdmiCecServiceArgument.UP:
            _process_volume(hdmi_network, KEY_VOLUME_UP, att)
        elif cmd == HdmiCecServiceArgument.DOWN:
            _process_volume(hdmi_network, KEY_VOLUME_DOWN, att)
        elif cmd == HdmiCecServiceArgument.MUTE:
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
    if HdmiCecServiceArgument.RAW in data:
        command = CecCommand(data[HdmiCecServiceArgument.RAW])
    else:
        src = data.get(HdmiCecServiceArgument.SRC, ADDR_UNREGISTERED)
        dst = data.get(HdmiCecServiceArgument.DST, ADDR_BROADCAST)
        if HdmiCecServiceArgument.CMD in data:
            cmd = data[HdmiCecServiceArgument.CMD]
        else:
            _LOGGER.error("Attribute 'cmd' is missing")
            return
        if HdmiCecServiceArgument.ATT in data:
            if isinstance(data[HdmiCecServiceArgument.ATT], (list,)):
                att = data[HdmiCecServiceArgument.ATT]
            else:
                att = reduce(
                    lambda x, y: f"{x}:{y:x}", data[HdmiCecServiceArgument.ATT]
                )
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
    if not (addr := call.data[HdmiCecServiceArgument.DEVICE]):
        _LOGGER.error("Device not found: %s", call.data[HdmiCecServiceArgument.DEVICE])
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
                    "Device %s has not physical address",
                    call.data[HdmiCecServiceArgument.DEVICE],
                )
                return
    if not isinstance(addr, (PhysicalAddress,)):
        addr = PhysicalAddress(addr)
    data.hdmi_network.active_source(addr)
    _LOGGER.debug("Selected %s (%s)", call.data[HdmiCecServiceArgument.DEVICE], addr)


def _update(call: ServiceCall) -> None:
    """Update if device update is needed.

    Called by service, requests CEC network to update data.
    """
    call.hass.data[DATA_HDMI_CEC].hdmi_network.scan()


def setup_services(hass: HomeAssistant) -> None:
    """Register the HDMI CEC services."""
    hass.services.register(
        DOMAIN, HdmiCecService.SEND_COMMAND, _tx, SERVICE_SEND_COMMAND_SCHEMA
    )
    hass.services.register(
        DOMAIN, HdmiCecService.VOLUME, _volume, schema=SERVICE_VOLUME_SCHEMA
    )
    hass.services.register(
        DOMAIN,
        HdmiCecService.UPDATE,
        _update,
        schema=SERVICE_UPDATE_DEVICES_SCHEMA,
    )
    hass.services.register(DOMAIN, HdmiCecService.POWER_ON, _power_on)
    hass.services.register(DOMAIN, HdmiCecService.STANDBY, _standby)
    hass.services.register(DOMAIN, HdmiCecService.SELECT_DEVICE, _select_device)
