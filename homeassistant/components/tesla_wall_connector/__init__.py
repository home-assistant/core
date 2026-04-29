"""The Tesla Wall Connector integration."""

from __future__ import annotations

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import WallConnectorError

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    WallConnectorConfigEntry,
    WallConnectorCoordinator,
    WallConnectorData,
    get_poll_interval,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: WallConnectorConfigEntry
) -> bool:
    """Set up Tesla Wall Connector from a config entry."""
    hostname = entry.data[CONF_HOST]

    wall_connector = WallConnector(host=hostname, session=async_get_clientsession(hass))

    try:
        version_data = await wall_connector.async_get_version()
    except WallConnectorError as ex:
        raise ConfigEntryNotReady from ex

    coordinator = WallConnectorCoordinator(hass, entry, hostname, wall_connector)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WallConnectorData(
        wall_connector_client=wall_connector,
        hostname=hostname,
        part_number=version_data.part_number,
        firmware_version=version_data.firmware_version,
        serial_number=version_data.serial_number,
        update_coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: WallConnectorConfigEntry) -> None:
    """Handle options update."""
    entry.runtime_data.update_coordinator.update_interval = get_poll_interval(entry)


async def async_unload_entry(
    hass: HomeAssistant, entry: WallConnectorConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
