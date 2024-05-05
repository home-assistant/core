"""The Nettigo Air Monitor component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import ClientConnectorError, ClientError
from nettigo_air_monitor import (
    ApiError,
    AuthFailedError,
    ConnectionOptions,
    NettigoAirMonitor,
)

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_SDS011, ATTR_SPS30, DOMAIN
from .coordinator import NAMDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]

NAMConfigEntry = ConfigEntry[NAMDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NAMConfigEntry) -> bool:
    """Set up Nettigo as config entry."""
    host: str = entry.data[CONF_HOST]
    username: str | None = entry.data.get(CONF_USERNAME)
    password: str | None = entry.data.get(CONF_PASSWORD)

    websession = async_get_clientsession(hass)

    options = ConnectionOptions(host=host, username=username, password=password)
    try:
        nam = await NettigoAirMonitor.create(websession, options)
    except (ApiError, ClientError, ClientConnectorError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    try:
        await nam.async_check_credentials()
    except ApiError as err:
        raise ConfigEntryNotReady from err
    except AuthFailedError as err:
        raise ConfigEntryAuthFailed from err

    if TYPE_CHECKING:
        assert entry.unique_id

    coordinator = NAMDataUpdateCoordinator(hass, nam, entry.unique_id)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove air_quality entities from registry if they exist
    ent_reg = er.async_get(hass)
    for sensor_type in ("sds", ATTR_SDS011, ATTR_SPS30):
        unique_id = f"{coordinator.unique_id}-{sensor_type}"
        if entity_id := ent_reg.async_get_entity_id(
            AIR_QUALITY_PLATFORM, DOMAIN, unique_id
        ):
            _LOGGER.debug("Removing deprecated air_quality entity %s", entity_id)
            ent_reg.async_remove(entity_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NAMConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
