"""The homely integration."""
from __future__ import annotations

from requests import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homelypy.homely import ConnectionFailedException, Homely

from .const import DOMAIN
from .sensors import PollingDataCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up homely from a config entry."""

    username = entry.data["username"]
    password = entry.data["password"]
    location_id = entry.data["location_id"]

    try:
        homely = Homely(username, password)
        location = await hass.async_add_executor_job(homely.get_location, location_id)
    except (ConnectionFailedException, ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Homely: {ex}") from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = homely

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator = PollingDataCoordinator(hass, homely, location)
    await coordinator.async_config_entry_first_refresh()

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    # hass.async_create_task(
    #     discovery.async_load_platform(
    #         hass,
    #         Platform.NOTIFY,
    #         DOMAIN,
    #         {CONF_NAME: DOMAIN},
    #         hass.data[DATA_HASS_CONFIG],
    #     )
    # )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
