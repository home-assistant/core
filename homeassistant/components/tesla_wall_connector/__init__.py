"""The Tesla Wall Connector integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import (
    WallConnectorConnectionError,
    WallConnectorConnectionTimeoutError,
    WallConnectorError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    WALLCONNECTOR_DATA_LIFETIME,
    WALLCONNECTOR_DATA_VITALS,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tesla Wall Connector from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hostname = entry.data[CONF_HOST]

    wall_connector = WallConnector(host=hostname, session=async_get_clientsession(hass))

    try:
        version_data = await wall_connector.async_get_version()
    except WallConnectorError as ex:
        raise ConfigEntryNotReady from ex

    async def async_update_data():
        """Fetch new data from the Wall Connector."""
        try:
            vitals = await wall_connector.async_get_vitals()
            lifetime = await wall_connector.async_get_lifetime()
        except WallConnectorConnectionTimeoutError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {hostname}: Timeout"
            ) from ex
        except WallConnectorConnectionError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {hostname}: Cannot"
                " connect"
            ) from ex
        except WallConnectorError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {hostname}: {ex}"
            ) from ex

        return {
            WALLCONNECTOR_DATA_VITALS: vitals,
            WALLCONNECTOR_DATA_LIFETIME: lifetime,
        }

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name="tesla-wallconnector",
        update_interval=get_poll_interval(entry),
        update_method=async_update_data,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = WallConnectorData(
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


def get_poll_interval(entry: ConfigEntry) -> timedelta:
    """Get the poll interval from config."""
    return timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    wall_connector_data: WallConnectorData = hass.data[DOMAIN][entry.entry_id]
    wall_connector_data.update_coordinator.update_interval = get_poll_interval(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@dataclass
class WallConnectorData:
    """Data for the Tesla Wall Connector integration."""

    wall_connector_client: WallConnector
    update_coordinator: DataUpdateCoordinator
    hostname: str
    part_number: str
    firmware_version: str
    serial_number: str
