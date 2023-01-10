"""The seitron integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from pyseitron.seitron_gateway import SeitronGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up seitron from a config entry."""

    async def _async_update_data() -> SeitronGateway:
        """Update data via library."""
        async with async_timeout.timeout(20):
            await seitron_gw.update()
        return seitron_gw

    coordinator = DataUpdateCoordinator[SeitronGateway](
        hass,
        _LOGGER,
        name=DOMAIN.title(),
        update_method=_async_update_data,
        update_interval=timedelta(seconds=60),
    )


    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    seitron_http_client = api.AsyncSeitronAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    seitron_gw = SeitronGateway(http_client=seitron_http_client)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
