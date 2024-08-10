"""The Oncue integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiooncue import LoginFailedException, Oncue, OncueDevice

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONNECTION_EXCEPTIONS, DOMAIN  # noqa: F401
from .types import OncueConfigEntry

PLATFORMS: list[str] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OncueConfigEntry) -> bool:
    """Set up Oncue from a config entry."""
    data = entry.data
    websession = async_get_clientsession(hass)
    client = Oncue(data[CONF_USERNAME], data[CONF_PASSWORD], websession)
    try:
        await client.async_login()
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex
    except LoginFailedException as ex:
        raise ConfigEntryAuthFailed from ex

    async def _async_update() -> dict[str, OncueDevice]:
        """Fetch data from Oncue."""
        try:
            return await client.async_fetch_all()
        except LoginFailedException as ex:
            raise ConfigEntryAuthFailed from ex

    coordinator = DataUpdateCoordinator[dict[str, OncueDevice]](
        hass,
        _LOGGER,
        name=f"Oncue {entry.data[CONF_USERNAME]}",
        update_interval=timedelta(minutes=10),
        update_method=_async_update,
        always_update=False,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OncueConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
