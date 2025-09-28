"""The Aurora ABB Powerone PV inverter sensor integration."""

# Reference info:
# https://s1.solacity.com/docs/PVI-3.0-3.6-4.2-OUTD-US%20Manual.pdf
# http://www.drhack.it/images/PDF/AuroraCommunicationProtocol_4_2.pdf
#
# Developer note:
# vscode devcontainer: use the following to access USB device:
# "runArgs": ["-e", "GIT_EDITOR=code --wait", "--device=/dev/ttyUSB0"],
# and add the following to the end of script/bootstrap:
# sudo chmod 777 /dev/ttyUSB0

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from .coordinator import AuroraAbbConfigEntry, AuroraAbbDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: AuroraAbbConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        new_data = {
            CONF_INVERTER_SERIAL_ADDRESS: entry.data["address"],
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_SERIAL_COMPORT: entry.data["port"],
        }

        hass.config_entries.async_update_entry(
            entry, data=new_data, minor_version=1, version=2
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: AuroraAbbConfigEntry) -> bool:
    """Set up Aurora ABB PowerOne from a config entry."""

    transport = entry.data[CONF_TRANSPORT]
    inverter_serial_address = entry.data[CONF_INVERTER_SERIAL_ADDRESS]

    if transport == TRANSPORT_SERIAL:
        serial_comport = entry.data[CONF_SERIAL_COMPORT]
        coordinator = AuroraAbbDataUpdateCoordinator(
            hass,
            entry,
            inverter_serial_address,
            transport,
            serial_comport=serial_comport,
        )
    elif transport == TRANSPORT_TCP:
        tcp_host = entry.data[CONF_TCP_HOST]
        tcp_port = entry.data[CONF_TCP_PORT]
        coordinator = AuroraAbbDataUpdateCoordinator(
            hass,
            entry,
            inverter_serial_address,
            transport,
            tcp_host=tcp_host,
            tcp_port=tcp_port,
        )
    else:
        raise ValueError(f"Unsupported transport type: {transport}")

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AuroraAbbConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
