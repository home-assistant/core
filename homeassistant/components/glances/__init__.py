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
from homeassistant.const import CONF_NAME, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_VERSION, DOMAIN
from .coordinator import GlancesDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Glances from config entry."""
    try:
        api = await get_api(hass, dict(config_entry.data))
    except GlancesApiAuthorizationError as err:
        raise ConfigEntryAuthFailed from err
    except GlancesApiError as err:
        raise ConfigEntryNotReady from err
    except UnknownError as err:
        raise ConfigEntryError(err) from err
    coordinator = GlancesDataUpdateCoordinator(hass, config_entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def get_api(hass: HomeAssistant, entry_data: dict[str, Any]) -> Glances:
    """Return the api from glances_api."""
    entry_data.pop(CONF_NAME, None)
    entry_data.pop(CONF_VERSION, None)

    httpx_client = get_async_client(hass, verify_ssl=entry_data[CONF_VERIFY_SSL])
    for version in (3, 2):
        api = Glances(httpx_client=httpx_client, version=version, **entry_data)
        try:
            await api.get_ha_sensor_data()
            _LOGGER.debug("Connected to Glances API v%s", version)
            if version == 2:
                async_create_issue(
                    hass,
                    DOMAIN,
                    "deprecated_version",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_version",
                )
            return api
        except GlancesApiNoDataAvailable as err:
            _LOGGER.debug("Failed to connect to Glances API v%s: %s", version, err)
    raise UnknownError("Could not connect to Glances API")


class UnknownError(HomeAssistantError):
    """Raise exception if we fail to connect to Glances API."""
