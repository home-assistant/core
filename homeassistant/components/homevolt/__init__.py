"""The Homevolt integration."""

from __future__ import annotations

from homevolt import Homevolt, HomevoltConnectionError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, HomevoltConfigEntry
from .coordinator import HomevoltDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Set up Homevolt from a config entry."""
    host: str = entry.data[CONF_HOST]
    password: str | None = entry.data.get(CONF_PASSWORD)

    websession = async_get_clientsession(hass)
    client = Homevolt(host, password, websession=websession)

    try:
        await client.update_info()
    except HomevoltConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Homevolt battery: {err}"
        ) from err

    coordinator = HomevoltDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.runtime_data:
            await entry.runtime_data.client.close_connection()
    return unload_ok
