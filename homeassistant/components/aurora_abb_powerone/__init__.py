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

from .aurora_client import AuroraClient
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


async def async_setup_entry(hass: HomeAssistant, entry: AuroraAbbConfigEntry) -> bool:
    """Set up Aurora ABB PowerOne from a config entry."""
    transport = entry.data[CONF_TRANSPORT]
    inverter_serial_address = entry.data[CONF_INVERTER_SERIAL_ADDRESS]

    if transport == TRANSPORT_SERIAL:
        client = AuroraClient.from_serial(
            inverter_serial_address=inverter_serial_address,
            serial_comport=entry.data[CONF_SERIAL_COMPORT],
        )
    elif transport == TRANSPORT_TCP:
        client = AuroraClient.from_tcp(
            inverter_serial_address=inverter_serial_address,
            tcp_host=entry.data[CONF_TCP_HOST],
            tcp_port=entry.data[CONF_TCP_PORT],
        )
    else:
        raise ValueError(f"Unsupported transport type: {transport}")

    coordinator = AuroraAbbDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AuroraAbbConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: AuroraAbbConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1 and entry.minor_version < 2:
        # Migrate from v1.1 to v1.2: add transport fields while keeping old keys
        address = entry.data.get("address")
        port = entry.data.get("port")
        if address is None or port is None:
            _LOGGER.error(
                "Config entry %s missing legacy address/port; cannot migrate to v1.2",
                entry.entry_id,
            )
            return False
        new_data = {
            **entry.data,
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_INVERTER_SERIAL_ADDRESS: address,
            CONF_SERIAL_COMPORT: port,
        }
        hass.config_entries.async_update_entry(
            entry, data=new_data, minor_version=2, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
