"""The Teltonika integration."""

import logging

from teltasync import Teltasync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import TeltonikaDataUpdateCoordinator
from .util import entry_data_to_url, url_to_entry_data

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type TeltonikaConfigEntry = ConfigEntry[TeltonikaDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> None:
    """Set up Teltonika from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    validate_ssl = entry.data.get(CONF_VERIFY_SSL, False)
    session = async_get_clientsession(hass)

    base_url = entry_data_to_url(entry.data)

    client = Teltasync(
        base_url=f"{base_url}/api",
        username=username,
        password=password,
        session=session,
        verify_ssl=validate_ssl,
    )

    # Create coordinator
    coordinator = TeltonikaDataUpdateCoordinator(hass, client, entry, base_url)

    # Fetch initial data and set up device info
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.device_info is not None

    # Store runtime data
    entry.runtime_data = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.client.close()


async def async_migrate_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> None:
    """Migrate a Teltonika config entry to the current version."""
    if entry.version == 1:
        # The host was stored as a URL, which DHCP rediscovery replaced with
        # a bare IP. Store the scheme and port separately so it only updates
        # the host.
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, **url_to_entry_data(entry.data[CONF_HOST])},
            version=2,
            minor_version=1,
        )
