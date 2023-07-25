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
from homeassistant.exceptions import ConfigEntryNotReady

from .const import APPLICATION, COORDINATOR, DOMAIN
from .coordinator import MyPermobilCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyPermobil from a config entry."""
    default: dict = {
        COORDINATOR: {},
    }
    hass.data.setdefault(DOMAIN, default)

    # create the API object from the config and save it in hass
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    p_api = MyPermobil(
        application=APPLICATION,
        session=session,
        email=entry.data.get(CONF_EMAIL),
        region=entry.data.get(CONF_REGION),
        code=entry.data.get(CONF_CODE),
        token=entry.data.get(CONF_TOKEN),
        expiration_date=entry.data.get(CONF_TTL),
    )
    try:
        p_api.self_authenticate()
    except MyPermobilClientException as err:
        _LOGGER.error("Permobil: %s", err)
        raise ConfigEntryNotReady(f"Permobil Config error for {p_api.email}") from err

    coordinator = MyPermobilCoordinator(hass, p_api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][COORDINATOR][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN][COORDINATOR].pop(entry.entry_id)
    return unload_ok
