"""Support for NuHeat thermostats."""

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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .account_identity import (
    InvalidAccountSubjectError,
    account_subject_from_entry_data,
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

PLATFORMS = [Platform.CLIMATE]


@dataclass(slots=True)
class NuHeatRuntimeData:
    """Runtime objects for a NuHeat account."""

    api: NuHeatClient
    coordinator: NuHeatCoordinator
    oauth_session: OAuth2Session


type NuHeatConfigEntry = ConfigEntry[NuHeatRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> bool:
    """Set up NuHeat from an OAuth config entry."""
    if is_pending_cleanup_entry(entry):
        # A deferred cleanup marker has no credentials and must never call the
        # obsolete API or create duplicate entities.
        return True
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
        await oauth_session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed("NuHeat authorization expired") from err
    except (OAuth2TokenRequestTransientError, OAuth2TokenRequestError) as err:
        raise ConfigEntryNotReady("Unable to refresh NuHeat authorization") from err

    api = NuHeatClient(async_get_clientsession(hass), async_access_token)
    coordinator = NuHeatCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NuHeatRuntimeData(api, coordinator, oauth_session)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not migration_reload_active():
        await async_resume_migration_cleanup(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> bool:
    """Unload NuHeat."""
    if is_pending_cleanup_entry(entry):
        return True
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry[Any]) -> bool:
    """Retain legacy entries until their user-assisted OAuth conversion."""
    if entry.version > OAUTH_CONFIG_ENTRY_VERSION:
        return False
    if is_legacy_entry(entry):
        # Legacy entries intentionally remain version 1 so their stored schema
        # is distinguishable and reversible until OAuth validation succeeds.
        return True
    if is_pending_cleanup_entry(entry):
        if entry.version < OAUTH_CONFIG_ENTRY_VERSION:
            hass.config_entries.async_update_entry(
                entry, version=OAUTH_CONFIG_ENTRY_VERSION
            )
        return True
    if entry.version < OAUTH_CONFIG_ENTRY_VERSION:
        try:
            account_subject = account_subject_from_entry_data(entry.data)
        except InvalidAccountSubjectError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="oauth_subject_migration_failed",
            ) from err

        if any(
            other.entry_id != entry.entry_id
            and other.unique_id == account_subject
            and not is_pending_cleanup_entry(other)
            for other in hass.config_entries.async_entries(DOMAIN)
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="oauth_subject_migration_duplicate",
            )
        hass.config_entries.async_update_entry(
            entry,
            unique_id=account_subject,
            version=OAUTH_CONFIG_ENTRY_VERSION,
        )
    return True
