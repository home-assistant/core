"""The TRMNL integration."""

from aiohttp import ClientError
from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import CLIENT_ID, DOMAIN
from .coordinator import TRMNLConfigEntry, TRMNLCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.TIME]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TRMNL OAuth client."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, "", name="TRMNL")
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Set up TRMNL from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    coordinator = TRMNLCoordinator(
        hass, entry, OAuth2Session(hass, entry, implementation)
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Trade the account API key of a version 1 entry for an OAuth token."""
    # Core also calls this for a newer minor version, which is already OAuth.
    if entry.version != 1:
        return
    client = TRMNLClient(
        token=entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )
    # TRMNL keeps one connection per name, and many installs share the location name "Home".
    name = f"{hass.config.location_name} ({(await instance_id.async_get(hass))[:8]})"
    try:
        token = await client.migrate_to_oauth(CLIENT_ID, name)
    except TRMNLAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="migration_failed"
        ) from err
    except (TRMNLError, TimeoutError, ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="migration_connection_error"
        ) from err

    # The user may have signed in to the same account with OAuth while this entry failed to load.
    if hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, token.sub):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="migration_duplicate"
        )

    hass.config_entries.async_update_entry(
        entry,
        unique_id=token.sub,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": token.access_token,
                "refresh_token": token.refresh_token,
                "token_type": token.token_type,
                "expires_in": token.expires_in,
                "scope": token.scope,
                "expires_at": token.created_at + token.expires_in,
            },
        },
        version=2,
    )
