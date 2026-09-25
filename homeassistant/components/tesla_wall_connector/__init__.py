"""The Tesla Wall Connector integration."""

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import WallConnectorError

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SPLIT_PHASE, DEFAULT_SPLIT_PHASE
from .coordinator import (
    WallConnectorConfigEntry,
    WallConnectorCoordinator,
    WallConnectorData,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: WallConnectorConfigEntry
) -> bool:
    """Set up Tesla Wall Connector from a config entry."""
    hostname = entry.data[CONF_HOST]

    wall_connector = WallConnector(
        host=hostname,
        session=async_get_clientsession(hass),
        split_phase=entry.options.get(CONF_SPLIT_PHASE, DEFAULT_SPLIT_PHASE),
    )

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

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WallConnectorConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
