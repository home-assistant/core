"""The blanco integration."""

import contextlib
import logging

from blanco_smart_home_api_client import BlancoApiClient, BlancoConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_APP_ID,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_TOKEN_TYPE,
    DOMAIN,
)
from .coordinator import BlancoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type BlancoConfigEntry = ConfigEntry[BlancoDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> bool:
    """Set up blanco from a config entry."""
    _LOGGER.debug("Setting up %s", DOMAIN)

    app_id = str(entry.data[CONF_APP_ID])
    coordinator = BlancoDataUpdateCoordinator(
        hass,
        entry=entry,
        token=entry.data[CONF_TOKEN],
        token_type=entry.data.get(CONF_TOKEN_TYPE, "Bearer"),
        dev_id=entry.data[CONF_DEV_ID],
        dev_type=entry.data.get(CONF_DEV_TYPE),
        serial=entry.data[CONF_SERIAL],
        app_id=app_id,
        app_version="",
        app_build="",
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> None:
    """Deregister the app from the BLANCO API when the integration is removed."""
    app_id = entry.data.get(CONF_APP_ID)
    token = entry.data.get(CONF_TOKEN)
    token_type = entry.data.get(CONF_TOKEN_TYPE, "Bearer")

    if not app_id or not token:
        return

    session = async_get_clientsession(hass)
    client = BlancoApiClient(
        session,
        app_id=app_id,
        token=str(token),
        token_type=str(token_type),
        os_version=HA_VERSION,
    )
    with contextlib.suppress(BlancoConnectionError):
        await client.deregister_app()
