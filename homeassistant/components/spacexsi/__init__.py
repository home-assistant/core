"""The SpaceXSI integration."""

from dataclasses import dataclass

from spacexai_subscription_client import (
    AuthenticationError,
    PermissionDeniedError,
    SpaceXAISubscriptionClient,
    SpaceXAISubscriptionError,
)
from spacexai_subscription_client.const import GROK_CLI_OAUTH_CLIENT_ID

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import AUTH_IMPLEMENTATION, DOMAIN

PLATFORMS = (Platform.CONVERSATION,)


@dataclass(slots=True)
class SpaceXSIData:
    """Runtime data for a SpaceXSI account."""

    oauth_session: OAuth2Session
    client: SpaceXAISubscriptionClient


type SpaceXSIConfigEntry = ConfigEntry[SpaceXSIData]


def create_client(hass: HomeAssistant) -> SpaceXAISubscriptionClient:
    """Create a SpaceXSI API client using Home Assistant HTTP sessions."""
    return SpaceXAISubscriptionClient(
        async_get_clientsession(hass),
        get_async_client(hass),
    )


async def async_setup_entry(hass: HomeAssistant, entry: SpaceXSIConfigEntry) -> bool:
    """Set up SpaceXSI from a config entry."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(GROK_CLI_OAUTH_CLIENT_ID, "", name="SpaceXSI"),
        auth_domain=AUTH_IMPLEMENTATION,
    )
    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session = OAuth2Session(hass, entry, implementation)
    try:
        await oauth_session.async_ensure_token_valid()
        client = create_client(hass)
        models = await client.async_list_models(oauth_session.token["access_token"])
    except (AuthenticationError, OAuth2TokenRequestReauthError, KeyError) as err:
        raise ConfigEntryAuthFailed from err
    except PermissionDeniedError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="not_entitled",
        ) from err
    except (SpaceXAISubscriptionError, OAuth2TokenRequestError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    if not models:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_models_available",
        )
    for subentry in entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue
        if (model := subentry.data[CONF_MODEL]) not in models:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="model_unavailable",
                translation_placeholders={"model": model},
            )

    entry.runtime_data = SpaceXSIData(oauth_session, client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpaceXSIConfigEntry) -> bool:
    """Unload a SpaceXSI config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
