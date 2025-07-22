"""The olarm integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp import ClientError, ClientResponseError
from olarmflowclient import OlarmFlowClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .coordinator import OlarmDataUpdateCoordinator
from .mqtt import OlarmFlowClientMQTT


@dataclass(kw_only=True)
class OlarmData:
    """A class that holds runtime data."""

    coordinator: OlarmDataUpdateCoordinator | None = None
    mqtt_client: OlarmFlowClientMQTT | None = None


_PLATFORMS = [
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up olarm from a config entry."""

    entry.runtime_data = OlarmData()

    # use oauth2 to get tokens
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()  # or auth.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed("OAuth session not valid") from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err
    _LOGGER.debug(
        "OAuth2 session ok, access_token expires at -> %s", session.token["expires_at"]
    )

    # setup OlarmFlow API and MQTT client
    olarm_client = OlarmFlowClient(session.token["access_token"])

    # setup coordinator
    coordinator = OlarmDataUpdateCoordinator(
        hass,
        entry,
        session,
        olarm_client,
    )
    entry.runtime_data.coordinator = coordinator

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
    await mqtt_client.init_mqtt()
    entry.runtime_data.mqtt_client = mqtt_client

    # setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    mqtt_client = entry.runtime_data.mqtt_client

    # stop mqtt
    await mqtt_client.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
