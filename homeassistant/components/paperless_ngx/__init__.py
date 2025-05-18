"""The Paperless-ngx integration."""

from __future__ import annotations

from typing import cast

from aiohttp import ClientConnectionError, ClientConnectorError
from pypaperless import Paperless
from pypaperless.exceptions import (
    InitializationError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    PaperlessConfigEntry,
    PaperlessCoordinator,
    PaperlessRuntimeData,
)


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Set up Paperless-ngx from a config entry."""
    data = cast(dict, entry.data)
    try:
        aiohttp_session = async_get_clientsession(hass)
        client = Paperless(
            url=data[CONF_HOST],
            token=data[CONF_ACCESS_TOKEN],
            session=aiohttp_session,
        )

        await client.initialize()

        coordinator = PaperlessCoordinator(hass, entry, client)
        await coordinator.async_config_entry_first_refresh()

    except (InitializationError, ClientConnectorError, ClientConnectionError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except PaperlessInvalidTokenError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except PaperlessInactiveOrDeletedError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="user_inactive_or_deleted",
        ) from err
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unknown",
        ) from err

    entry.runtime_data = PaperlessRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessConfigEntry) -> bool:
    """Unload paperless-ngx config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
