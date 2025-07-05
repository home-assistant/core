"""The Paperless-ngx integration."""

from pypaperless import Paperless
from pypaperless.exceptions import (
    InitializationError,
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import (
    PaperlessConfigEntry,
    PaperlessData,
    PaperlessStatisticCoordinator,
    PaperlessStatusCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.UPDATE]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Set up Paperless-ngx from a config entry."""

    api = await _get_paperless_api(hass, entry)

    statistics_coordinator = PaperlessStatisticCoordinator(hass, entry, api)
    status_coordinator = PaperlessStatusCoordinator(hass, entry, api)

    await statistics_coordinator.async_config_entry_first_refresh()

    try:
        await status_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        # Catch the error so the integration doesn't fail just because status coordinator fails.
        LOGGER.warning("Could not initialize status coordinator: %s", err)

    entry.runtime_data = PaperlessData(
        status=status_coordinator,
        statistics=statistics_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Unload paperless-ngx config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _get_paperless_api(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
) -> Paperless:
    """Create and initialize paperless-ngx API."""

    api = Paperless(
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass, entry.data.get(CONF_VERIFY_SSL, True)),
    )

    try:
        await api.initialize()
        await api.statistics()  # test permissions on api
    except PaperlessConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except PaperlessInvalidTokenError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_api_key",
        ) from err
    except PaperlessInactiveOrDeletedError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="user_inactive_or_deleted",
        ) from err
    except PaperlessForbiddenError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="forbidden",
        ) from err
    except InitializationError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    else:
        return api
