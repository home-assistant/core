"""The Place integration."""

import logging

from aiohttp import ClientResponseError
from place.auth import get_iot_credentials
from place.config import IOT_ENDPOINT
from place.mqtt_client import MqttClient
from place.provider import Provider

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import oauth2
from .const import DOMAIN
from .coordinator import PlaceConfigEntry, PlaceCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PlaceConfigEntry) -> bool:
    """Set up Place from a config entry."""
    auth_implementation = oauth2.SRPAuthImplementation(hass, DOMAIN)
    try:
        await auth_implementation.async_refresh_token(entry.data["token"])
    except ClientResponseError as err:
        raise ConfigEntryAuthFailed(err) from err

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
    await provider.enable()

    # Exchange the stored Cognito ID token for AWS IoT credentials
    token = entry.data["token"]
    credentials = await hass.async_add_executor_job(
        get_iot_credentials, token["id_token"], token["access_token"]
    )

    mqtt_client = MqttClient(endpoint=IOT_ENDPOINT, credentials=credentials)

    coordinator = PlaceCoordinator(hass, entry, provider, mqtt_client)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlaceConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
