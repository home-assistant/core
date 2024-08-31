"""The MyPermobil integration."""
from __future__ import annotations

import logging

from mypermobil import MyPermobil, MyPermobilClientException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    CONF_EMAIL,
    CONF_REGION,
    CONF_TOKEN,
    CONF_TTL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import APPLICATION, DOMAIN
from .coordinator import MyPermobilCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyPermobil from a config entry."""

    # create the API object from the config and save it in hass
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    p_api = MyPermobil(
        application=APPLICATION,
        session=session,
        email=entry.data[CONF_EMAIL],
        region=entry.data[CONF_REGION],
        code=entry.data[CONF_CODE],
        token=entry.data[CONF_TOKEN],
        expiration_date=entry.data[CONF_TTL],
    )
    try:
        p_api.self_authenticate()
    except MyPermobilClientException as err:
        _LOGGER.error("Error authenticating  %s", err)
        raise ConfigEntryAuthFailed(f"Config error for {p_api.email}") from err

    # create the coordinator with the API object
    coordinator = MyPermobilCoordinator(hass, p_api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
