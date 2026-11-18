"""The Place integration."""

from asyncio import run_coroutine_threadsafe
import logging

from aiohttp import ClientError
from place.auth import get_iot_credentials
from place.config import IOT_ENDPOINT
from place.errors import (
    PlaceCredentialExchangeAuthError,
    PlaceCredentialExchangeConnectionError,
    PlaceFulfillmentError,
)
from place.models import Credentials
from place.mqtt_client import MqttClient
from place.provider import Provider

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestBaseError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import oauth2
from .const import DOMAIN
from .coordinator import (
    PlaceConfigEntry,
    PlaceCoordinator,
    raise_mapped_fulfillment_error,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PlaceConfigEntry) -> None:
    """Set up Place from a config entry."""
    auth_implementation = oauth2.SRPAuthImplementation(hass, DOMAIN)
    try:
        token = await auth_implementation.async_refresh_token(entry.data["token"])
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except OAuth2TokenRequestBaseError as err:
        raise ConfigEntryNotReady(err) from err

    hass.config_entries.async_update_entry(entry, data={**entry.data, "token": token})

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, auth_implementation
    )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    authenticated_session = oauth2.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    provider = Provider(authenticated_session)
    try:
        await provider.enable()
    except (ClientError, PlaceFulfillmentError) as err:
        raise_mapped_fulfillment_error(err)

    # Exchange the stored Cognito ID token for AWS IoT credentials
    token = entry.data["token"]
    try:
        credentials = await hass.async_add_executor_job(
            get_iot_credentials, token["id_token"], token["access_token"]
        )
    except PlaceCredentialExchangeAuthError as err:
        raise ConfigEntryAuthFailed(err) from err
    except PlaceCredentialExchangeConnectionError as err:
        raise ConfigEntryNotReady(err) from err

    async def async_get_tokens() -> tuple[str, str]:
        """Get current OAuth tokens on the event loop."""
        await session.async_ensure_token_valid()
        token = session.token
        return token["id_token"], token["access_token"]

    def refresh_credentials() -> Credentials:
        """Exchange valid OAuth tokens for MQTT credentials on reconnect."""
        id_token, access_token = run_coroutine_threadsafe(
            async_get_tokens(), hass.loop
        ).result()
        return get_iot_credentials(id_token, access_token)

    mqtt_client = MqttClient(
        endpoint=IOT_ENDPOINT,
        credentials=credentials,
        credentials_provider=refresh_credentials,
    )

    coordinator = PlaceCoordinator(hass, entry, provider, mqtt_client)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: PlaceConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
