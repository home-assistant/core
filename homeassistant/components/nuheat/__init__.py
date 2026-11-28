"""Support for NuHeat thermostats."""

from asyncio import timeout
from dataclasses import dataclass
from typing import Any

from chemelex_nuheat import NuHeatApiError, NuHeatAuthError, NuHeatClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import DOMAIN
from .coordinator import NuHeatCoordinator
from .migration import (
    OAUTH_CONFIG_ENTRY_VERSION,
    async_resume_migration_cleanup,
    is_legacy_entry,
    is_pending_cleanup_entry,
    migration_reload_active,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.CLIMATE]


@dataclass(slots=True)
class NuHeatRuntimeData:
    """Runtime objects for a NuHeat account."""

    api: NuHeatClient
    coordinator: NuHeatCoordinator
    oauth_session: OAuth2Session


type NuHeatConfigEntry = ConfigEntry[NuHeatRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> None:
    """Set up NuHeat from an OAuth config entry."""
    if is_pending_cleanup_entry(entry):
        # Deleting the initiating entry during reauth would abort its flow.
        return
    if is_legacy_entry(entry):
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="legacy_migration_required",
        )

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "NuHeat OAuth implementation temporarily unavailable"
        ) from err

    oauth_session = OAuth2Session(hass, entry, implementation)

    async def async_access_token(force_refresh: bool) -> str:
        if force_refresh:
            token = {**oauth_session.token, "expires_at": 0}
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_TOKEN: token}
            )
        try:
            await oauth_session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise NuHeatAuthError("NuHeat authorization expired") from err
        except (OAuth2TokenRequestTransientError, OAuth2TokenRequestError) as err:
            raise NuHeatApiError("Unable to refresh NuHeat authorization") from err
        return oauth_session.token["access_token"]

    try:
        async with timeout(30):
            await oauth_session.async_ensure_token_valid()
    except TimeoutError as err:
        raise ConfigEntryNotReady("NuHeat token validation timed out") from err
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed("NuHeat authorization expired") from err
    except (OAuth2TokenRequestTransientError, OAuth2TokenRequestError) as err:
        raise ConfigEntryNotReady("Unable to refresh NuHeat authorization") from err

    api = NuHeatClient(
        async_get_clientsession(hass), async_access_token, include_schedule_details=True
    )
    coordinator = NuHeatCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise

    entry.runtime_data = NuHeatRuntimeData(api, coordinator, oauth_session)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not migration_reload_active():
        await async_resume_migration_cleanup(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> None:
    """Unload NuHeat."""
    if is_pending_cleanup_entry(entry):
        return
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry[Any]) -> None:
    """Retain legacy entries until their user-assisted OAuth conversion."""
    if is_legacy_entry(entry):
        # Legacy entries intentionally remain version 1 so their stored schema
        # is distinguishable and reversible until OAuth validation succeeds.
        return
    if is_pending_cleanup_entry(entry):
        if entry.version < OAUTH_CONFIG_ENTRY_VERSION:
            hass.config_entries.async_update_entry(
                entry, version=OAUTH_CONFIG_ENTRY_VERSION
            )
        return
    if entry.version < OAUTH_CONFIG_ENTRY_VERSION:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_configuration_version",
        )
