"""The Aurora ABB Powerone PV inverter sensor integration."""

# Reference info:
# https://s1.solacity.com/docs/PVI-3.0-3.6-4.2-OUTD-US%20Manual.pdf
# http://www.drhack.it/images/PDF/AuroraCommunicationProtocol_4_2.pdf
#
# Developer note:
# vscode devcontainer: use the following to access USB device:
# "runArgs": ["-e", "GIT_EDITOR=code --wait", "--device=/dev/ttyUSB0"],

import logging

from aurorapy.client import AuroraSerialClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aurora ABB PowerOne from a config entry."""

    comport = entry.data[CONF_PORT]
    address = entry.data[CONF_ADDRESS]
    serclient = AuroraSerialClient(address, comport, parity="N", timeout=1)

    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = serclient

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # It should not be necessary to close the serial port because we close
    # it after every use in sensor.py, i.e. no need to do entry["client"].close()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok
