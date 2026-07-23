"""The Beatbot integration."""

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .api import BeatbotAPI
from .config_flow import BeatbotOAuth2Implementation
from .coordinator import BeatbotCoordinator
from .iot.const import DOMAIN, SUPPORTED_PLATFORMS
from .iot.event_stream import BeatbotEventClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class BeatbotRuntimeData:
    """Runtime objects owned by a Beatbot config entry."""

    coordinator: BeatbotCoordinator
    api: BeatbotAPI
    session: config_entry_oauth2_flow.OAuth2Session
    event_client: BeatbotEventClient


type BeatbotConfigEntry = ConfigEntry[BeatbotRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BeatbotConfigEntry) -> bool:
    """Set up Beatbot from a config entry."""
    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )
    if DOMAIN not in implementations:
        config_entry_oauth2_flow.async_register_implementation(
            hass, DOMAIN, BeatbotOAuth2Implementation(hass)
        )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    api = BeatbotAPI(hass, entry, session)
    coordinator = BeatbotCoordinator(hass, api, entry)

    await coordinator.async_config_entry_first_refresh()

    event_client = BeatbotEventClient(hass, entry, session, api, coordinator)
    entry.runtime_data = BeatbotRuntimeData(
        coordinator=coordinator,
        api=api,
        session=session,
        event_client=event_client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)
    event_client.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BeatbotConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS):
        return False
    # Cancel any post-control refresh tasks still sleeping in their delay
    # window before tearing down the coordinator/api/session they close over.
    await entry.runtime_data.event_client.async_stop()
    entry.runtime_data.coordinator.async_cancel_pending_refreshes()
    return True
