"""The SpaceXAI integration."""

from dataclasses import dataclass

from spacexai_subscription_client import (
    AuthenticationError,
    PermissionDeniedError,
    SpaceXAISubscriptionClient,
    SpaceXAISubscriptionError,
)
from spacexai_subscription_client.const import (
    AUTHORIZE_URL,
    GROK_CLI_OAUTH_CLIENT_ID,
    TOKEN_URL,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
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
    LocalOAuth2Implementation,
    OAuth2Session,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

PLATFORMS = (Platform.CONVERSATION,)


@dataclass(slots=True)
class SpaceXAIData:
    """Runtime data for a SpaceXAI account."""

    oauth_session: OAuth2Session
    client: SpaceXAISubscriptionClient


type SpaceXAIConfigEntry = ConfigEntry[SpaceXAIData]


def oauth_implementation(hass: HomeAssistant) -> LocalOAuth2Implementation:
    """Return the public OAuth implementation used by Grok CLI."""
    return LocalOAuth2Implementation(
        hass=hass,
        domain=DOMAIN,
        client_id=GROK_CLI_OAUTH_CLIENT_ID,
        client_secret="",
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
    )


def create_client(hass: HomeAssistant) -> SpaceXAISubscriptionClient:
    """Create a SpaceXAI API client using Home Assistant HTTP sessions."""
    return SpaceXAISubscriptionClient(
        async_get_clientsession(hass),
        get_async_client(hass),
    )


async def async_setup_entry(hass: HomeAssistant, entry: SpaceXAIConfigEntry) -> bool:
    """Set up SpaceXAI from a config entry."""
    oauth_session = OAuth2Session(hass, entry, oauth_implementation(hass))
    try:
        await oauth_session.async_ensure_token_valid()
        client = create_client(hass)
        if not await client.async_list_models(oauth_session.token["access_token"]):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_models_available",
            )
    except (AuthenticationError, OAuth2TokenRequestReauthError, KeyError) as err:
        raise ConfigEntryAuthFailed from err
    except PermissionDeniedError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="not_entitled",
        ) from err
    except (SpaceXAISubscriptionError, OAuth2TokenRequestError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = SpaceXAIData(oauth_session, client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpaceXAIConfigEntry) -> bool:
    """Unload a SpaceXAI config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
