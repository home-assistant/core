"""Voice support: the Voice app, and what the Assist pipeline asks of it.

The app is installed from the OHF Voice apps repository and announces itself
through the Supervisor; there is nothing to set up or configure. It watches
a run's audio and says whether that was the wake word and where the command
begins and ends.

This integration owns the app -- installed, reachable, what it can do today
-- which is why the pipeline depends on it rather than the other way round.
The pipeline asks ``async_get_client`` each run.

Whether the person wants one at all is a Labs preview feature, and not a
switch over an answer collected anyway: a satellite told to send its wake
word audio detects at a lower threshold, so turning it off has to leave the
pipeline exactly as it was.
"""

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
    """Return the app the pipeline should use this run, if there is one.

    Asked per run rather than held, because every reason there might not be
    one -- app stopped, entry unloaded, preview feature off -- can change
    between runs.
    """
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

    # What it can verify follows the models it has, and an update can change
    # those without moving the app, so this is asked again now and then.
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
    """Unload a config entry.

    Everything was registered with ``async_on_unload``, and the pipeline
    asks per run, so an unloaded entry is already one it will not find.
    """
