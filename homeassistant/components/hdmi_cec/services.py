"""Services for the HDMI CEC integration."""

from dataclasses import dataclass
import logging

import probatio
from pycec.network import HDMINetwork, PhysicalAddress

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DATA_HDMI_CEC, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = "device"

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
        DOMAIN,
        SERVICE_UPDATE_DEVICES,
        _update,
        schema=SERVICE_UPDATE_DEVICES_SCHEMA,
    )
    hass.services.register(DOMAIN, SERVICE_POWER_ON, _power_on)
    hass.services.register(DOMAIN, SERVICE_STANDBY, _standby)
    hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE, _select_device)
