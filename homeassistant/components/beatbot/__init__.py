"""The Beatbot integration."""

from dataclasses import dataclass
from typing import Any

from beatbot_cloud import BeatbotAuthenticationError, BeatbotClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import PLATFORMS
from .coordinator import BeatbotCoordinator
from .event_stream import BeatbotEventClient


@dataclass
class BeatbotRuntimeData:
    """Runtime objects owned by a Beatbot config entry."""

    coordinator: BeatbotCoordinator
    api: BeatbotClient
    session: config_entry_oauth2_flow.OAuth2Session
    event_client: BeatbotEventClient


type BeatbotConfigEntry = ConfigEntry[BeatbotRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BeatbotConfigEntry) -> bool:
    """Set up Beatbot from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    async def _async_request(method: str, url: str, **kwargs: Any) -> Any:
        try:
            return await session.async_request(method, url, **kwargs)
        except OAuth2TokenRequestReauthError as err:
            raise BeatbotAuthenticationError from err

    api = BeatbotClient(entry.data["region"], _async_request)
    coordinator = BeatbotCoordinator(hass, api, entry)

    await coordinator.async_config_entry_first_refresh()

    event_client = BeatbotEventClient(hass, entry, session, api, coordinator)
    entry.runtime_data = BeatbotRuntimeData(
        coordinator=coordinator,
        api=api,
        session=session,
        event_client=event_client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    event_client.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeatbotConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.event_client.async_stop()
    return True
