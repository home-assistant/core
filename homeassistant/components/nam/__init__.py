"""The Nettigo Air Monitor component."""

from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError
from nettigo_air_monitor import (
    ApiError,
    AuthFailedError,
    ConnectionOptions,
    NettigoAirMonitor,
)

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_SDS011, ATTR_SPS30, DOMAIN
from .coordinator import NAMConfigEntry, NAMDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NAMConfigEntry) -> bool:
    """Set up Nettigo as config entry."""
    host: str = entry.data[CONF_HOST]
    username: str | None = entry.data.get(CONF_USERNAME)
    password: str | None = entry.data.get(CONF_PASSWORD)

    websession = async_get_clientsession(hass)

    options = ConnectionOptions(host=host, username=username, password=password)
    try:
        nam = await NettigoAirMonitor.create(websession, options)
    except (ApiError, ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_communication_error",
            translation_placeholders={"device": entry.title},
        ) from err

    try:
        await nam.async_check_credentials()
    except (ApiError, ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_communication_error",
            translation_placeholders={"device": entry.title},
        ) from err
    except AuthFailedError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_error",
            translation_placeholders={"device": entry.title},
        ) from err

    coordinator = NAMDataUpdateCoordinator(hass, entry, nam)
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
