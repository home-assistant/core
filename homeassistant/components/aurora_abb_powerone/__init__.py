"""The Aurora ABB Powerone PV inverter sensor integration."""

# Reference info:
# https://s1.solacity.com/docs/PVI-3.0-3.6-4.2-OUTD-US%20Manual.pdf
# http://www.drhack.it/images/PDF/AuroraCommunicationProtocol_4_2.pdf
#
# Developer note:
# vscode devcontainer: use the following to access USB device:
# "runArgs": ["-e", "GIT_EDITOR=code --wait", "--device=/dev/ttyUSB0"],

import logging

from aurorapy.client import AuroraError, AuroraSerialClient, AuroraTCPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS  # Bus address
from homeassistant.const import CONF_HOST  # Network address
from homeassistant.const import CONF_PORT  # RS485 Device or TCP
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import validate_and_connect
from .const import ATTR_SERIAL_NUMBER, DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aurora ABB PowerOne from a config entry."""
    comport = entry.data[CONF_PORT]
    address = entry.data[CONF_ADDRESS]

    if entry.data[CONF_PORT] == "TCP":
        ip, __, port = entry.data[CONF_HOST].rpartition(":")
        client = AuroraTCPClient(ip=ip, port=int(port), address=address)
    else:
        client = AuroraSerialClient(address, comport, parity="N", timeout=1)

    # To handle yaml import attempts in darkness, (re)try connecting only if
    # unique_id not yet assigned.
    if entry.unique_id is None:
        try:
            res = await hass.async_add_executor_job(
                validate_and_connect, hass, entry.data
            )
        except AuroraError as error:
            if "No response after" in str(error):
                raise ConfigEntryNotReady("No response (could be dark)") from error
            _LOGGER.error("Failed to connect to inverter: %s", error)
            return False
        except OSError as error:
            if error.errno == 19:  # No such device.
                _LOGGER.error("Failed to connect to inverter: no such COM port")
                return False
            _LOGGER.error("Failed to connect to inverter: %s", error)
            return False
        else:
            # If we got here, the device is now communicating (maybe after
            # being in darkness). But there's a small risk that the user has
            # configured via the UI since we last attempted the yaml setup,
            # which means we'd get a duplicate unique ID.
            new_id = res[ATTR_SERIAL_NUMBER]
            # Check if this unique_id has already been used
            for existing_entry in hass.config_entries.async_entries(DOMAIN):
                if existing_entry.unique_id == new_id:
                    _LOGGER.debug(
                        "Remove already configured config entry for id %s", new_id
                    )
                    hass.async_create_task(
                        hass.config_entries.async_remove(entry.entry_id)
                    )
                    return False
            hass.config_entries.async_update_entry(entry, unique_id=new_id)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # It should not be necessary to close the serial port because we close
    # it after every use in sensor.py, i.e. no need to do entry["client"].close()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
