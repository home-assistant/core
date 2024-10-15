"""The Glances component."""

import logging
from typing import Any

from glances_api import Glances
from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiError,
    GlancesApiNoDataAvailable,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN
from .coordinator import GlancesDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)

type GlancesConfigEntry = ConfigEntry[GlancesDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GlancesConfigEntry
) -> bool:
    """Set up Glances from config entry."""
    try:
        api = await get_api(hass, dict(config_entry.data))
    except GlancesApiAuthorizationError as err:
        raise ConfigEntryAuthFailed from err
    except GlancesApiError as err:
        raise ConfigEntryNotReady from err
    except ServerVersionMismatch as err:
        raise ConfigEntryError(err) from err
    coordinator = GlancesDataUpdateCoordinator(hass, config_entry, api)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GlancesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def get_api(hass: HomeAssistant, entry_data: dict[str, Any]) -> Glances:
    """Return the api from glances_api."""
    httpx_client = get_async_client(hass, verify_ssl=entry_data[CONF_VERIFY_SSL])
    for version in (4, 3, 2):
        api = Glances(
            host=entry_data[CONF_HOST],
            port=entry_data[CONF_PORT],
            version=version,
            ssl=entry_data[CONF_SSL],
            username=entry_data.get(CONF_USERNAME),
            password=entry_data.get(CONF_PASSWORD),
            httpx_client=httpx_client,
        )
        try:
            await api.get_ha_sensor_data()
        except GlancesApiNoDataAvailable as err:
            _LOGGER.debug("Failed to connect to Glances API v%s: %s", version, err)
            continue
        if version == 2:
            async_create_issue(
                hass,
                DOMAIN,
                "deprecated_version",
                breaks_in_ha_version="2024.8.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_version",
            )
        _LOGGER.debug("Connected to Glances API v%s", version)
        return api
    raise ServerVersionMismatch("Could not connect to Glances API version 2, 3 or 4")


class ServerVersionMismatch(HomeAssistantError):
    """Raise exception if we fail to connect to Glances API."""
