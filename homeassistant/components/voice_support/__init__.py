"""The Voice support integration."""

from datetime import datetime, timedelta

import aiohttp

from homeassistant.components.labs import async_is_preview_feature_enabled
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .client import VoiceSupportClient
from .const import (
    DOMAIN,
    INFO_INTERVAL_MINUTES,
    LOGGER,
    PREVIEW_FEATURE_WAKE_WORD_VERIFICATION,
)
from .run import (
    AudioRun,
    AudioRunRequest,
    SpeechEnded,
    SpeechStarted,
    WakeWordAccepted,
    WakeWordRejected,
)

__all__ = (
    "AudioRun",
    "AudioRunRequest",
    "SpeechEnded",
    "SpeechStarted",
    "VoiceSupportClient",
    "WakeWordAccepted",
    "WakeWordRejected",
    "async_get_client",
)

type VoiceSupportConfigEntry = ConfigEntry[VoiceSupportClient]


@callback
def async_get_client(hass: HomeAssistant) -> VoiceSupportClient | None:
    """Return the Voice app client, if the app is set up and enabled."""
    if not async_is_preview_feature_enabled(
        hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION
    ):
        return None

    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        client: VoiceSupportClient = entry.runtime_data
        return client
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: VoiceSupportConfigEntry
) -> None:
    """Set up the app from a config entry."""
    client = VoiceSupportClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])

    try:
        info = await client.async_update_info()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise ConfigEntryNotReady(f"Cannot reach the app at {client.url}") from err

    LOGGER.debug("Connected to %s %s at %s", info.name, info.version, client.url)
    entry.runtime_data = client

    async def _refresh(_now: datetime) -> None:
        try:
            await client.async_update_info()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            LOGGER.debug("Cannot reach %s: %s", client.url, err)

    entry.async_on_unload(
        async_track_time_interval(
            hass, _refresh, timedelta(minutes=INFO_INTERVAL_MINUTES)
        )
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: VoiceSupportConfigEntry
) -> None:
    """Unload a config entry."""
