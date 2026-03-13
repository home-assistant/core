"""The olarm integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp import ClientError, ClientResponseError
from olarmflowclient import MqttConnectError, MqttTimeoutError, OlarmFlowClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .coordinator import OlarmDataUpdateCoordinator
from .mqtt import OlarmFlowClientMQTT


@dataclass(kw_only=True)
class OlarmData:
    """A class that holds runtime data."""

    coordinator: OlarmDataUpdateCoordinator
    mqtt_client: OlarmFlowClientMQTT


type OlarmConfigEntry = ConfigEntry[OlarmData]

_PLATFORMS = [
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OlarmConfigEntry) -> bool:
    """Set up olarm from a config entry."""

    # use oauth2 to get tokens
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable, will retry"
        ) from err
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryError("OAuth session not valid") from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err
    _LOGGER.debug(
        "OAuth2 session ok, access_token expires at -> %s", session.token["expires_at"]
    )

    # setup OlarmFlow API and MQTT client
    olarm_client = OlarmFlowClient(
        session.token["access_token"], session.token["expires_at"]
    )

    # setup coordinator
    coordinator = OlarmDataUpdateCoordinator(
        hass,
        entry,
        session,
        olarm_client,
    )

    # Fetch initial data using DataUpdateCoordinator pattern
    await coordinator.async_config_entry_first_refresh()

    # setup and start mqtt
    mqtt_client = OlarmFlowClientMQTT(
        hass,
        entry,
        session,
        olarm_client,
        coordinator,
    )
    try:
        await mqtt_client.init_mqtt()
    except (MqttTimeoutError, MqttConnectError) as err:
        raise ConfigEntryNotReady(f"Failed to connect to Olarm MQTT: {err}") from err

    # Set runtime data
    entry.runtime_data = OlarmData(
        coordinator=coordinator,
        mqtt_client=mqtt_client,
    )

    # setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OlarmConfigEntry) -> bool:
    """Unload a config entry."""
    mqtt_client = entry.runtime_data.mqtt_client

    # Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    # Only stop MQTT if unload was successful
    if unload_ok:
        try:
            await mqtt_client.async_stop()
        except Exception:
            _LOGGER.exception("Error stopping MQTT client during unload")

    return unload_ok
