"""The Voice support integration."""

from collections.abc import AsyncIterable
from datetime import datetime, timedelta
import logging

from homeassistant.components.hassio import AddonError
from homeassistant.components.labs import (
    EventLabsUpdatedData,
    async_is_preview_feature_enabled,
    async_subscribe_preview_feature,
)
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .app import get_app_manager
from .client import (
    API_VERSION,
    CLIENT_ERRORS,
    AudioRun,
    AudioRunRequest,
    UnsupportedVersionError,
    VoiceSupportClient,
    WakeWordAccepted,
    WakeWordRejected,
)
from .const import CONF_INTEGRATION_CREATED_APP, DOMAIN

__all__ = [
    "DOMAIN",
    "AudioRun",
    "AudioRunRequest",
    "WakeWordAccepted",
    "WakeWordRejected",
    "async_on_wake_words_changed",
    "async_start_run",
    "async_verifies_wake_word",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

INFO_REFRESH_INTERVAL = timedelta(minutes=5)

PREVIEW_FEATURE_NEXT_GENERATION_VOICE = "next_generation_voice"

DATA_CLIENT: HassKey[VoiceSupportClient] = HassKey(DOMAIN)
DATA_LISTENERS: HassKey[list[CALLBACK_TYPE]] = HassKey(f"{DOMAIN}_listeners")

_LOGGER = logging.getLogger(__name__)


@callback
def async_is_enabled(hass: HomeAssistant) -> bool:
    """Whether the person has turned voice support on."""
    return async_is_preview_feature_enabled(
        hass, DOMAIN, PREVIEW_FEATURE_NEXT_GENERATION_VOICE
    )


@callback
def async_verifies_wake_word(hass: HomeAssistant, wake_word: str) -> bool:
    """Whether the app can second-guess this wake word right now.

    False is the answer for every reason there might not be one: no app, an
    app that has no model for this wake word, or a person who has not asked
    for any of it.
    """
    if not async_is_enabled(hass):
        return False
    if (client := hass.data.get(DATA_CLIENT)) is None:
        return False
    return client.supports_wake_word(wake_word)


@callback
def async_on_wake_words_changed(
    hass: HomeAssistant, listener: CALLBACK_TYPE
) -> CALLBACK_TYPE:
    """Listen for verification support changes and return a removal callback."""
    listeners = hass.data.setdefault(DATA_LISTENERS, [])
    listeners.append(listener)

    @callback
    def _remove() -> None:
        listeners.remove(listener)

    return _remove


@callback
def _async_wake_words_changed(hass: HomeAssistant) -> None:
    """Tell satellites the answer may have moved."""
    for listener in hass.data.get(DATA_LISTENERS, []).copy():
        listener()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up voice support."""

    async def _async_preview_feature_updated(event_data: EventLabsUpdatedData) -> None:
        if event_data["enabled"]:
            _async_provision(hass)
        else:
            for entry in hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_INTEGRATION_CREATED_APP):
                    await hass.config_entries.async_remove(entry.entry_id)
        _async_wake_words_changed(hass)

    async_subscribe_preview_feature(
        hass,
        DOMAIN,
        PREVIEW_FEATURE_NEXT_GENERATION_VOICE,
        _async_preview_feature_updated,
    )
    _async_provision(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Connect to the app at the entry's address."""
    client = VoiceSupportClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        await client.async_update_info()
    except CLIENT_ERRORS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"url": str(client.url)},
        ) from err
    except UnsupportedVersionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unsupported_version",
            translation_placeholders={
                "name": err.info.name,
                "version": err.info.version,
                "api_version": str(err.info.api_version),
                "supported_api_version": str(API_VERSION),
            },
        ) from err
    finally:
        if entry.data.get(CONF_INTEGRATION_CREATED_APP):
            get_app_manager(hass).async_schedule_update_addon(catch_error=True)

    async def _async_refresh_info(_now: datetime) -> None:
        previous_info = client.info
        try:
            info = await client.async_update_info()
        except (*CLIENT_ERRORS, UnsupportedVersionError) as err:
            _LOGGER.debug("Cannot use the app at %s (%r)", client.url, err)
            hass.config_entries.async_schedule_reload(entry.entry_id)
        else:
            if (
                previous_info is None
                or previous_info.wake_words.keys() != info.wake_words.keys()
            ):
                _async_wake_words_changed(hass)

    entry.async_on_unload(
        async_track_time_interval(hass, _async_refresh_info, INFO_REFRESH_INTERVAL)
    )
    hass.data[DATA_CLIENT] = client
    _async_wake_words_changed(hass)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload the entry."""
    hass.data.pop(DATA_CLIENT)
    _async_wake_words_changed(hass)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Uninstall the app along with the entry, if this integration installed it."""
    if not entry.data.get(CONF_INTEGRATION_CREATED_APP):
        return

    app_manager = get_app_manager(hass)
    try:
        await app_manager.async_stop_addon()
        await app_manager.async_create_backup()
        await app_manager.async_uninstall_addon()
    except AddonError as err:
        _LOGGER.error(err)


@callback
def _async_provision(hass: HomeAssistant) -> None:
    """Put what voice support needs in place, unless that is done or underway.

    On a Supervised system that is the app. Nothing happens on a system
    without one: there the user says where the app runs.
    """
    if not is_hassio(hass):
        return
    if not async_is_enabled(hass):
        return
    if hass.config_entries.async_has_entries(DOMAIN):
        return
    if hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        return
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )


async def async_start_run(
    hass: HomeAssistant, request: AudioRunRequest, audio: AsyncIterable[bytes]
) -> AudioRun | None:
    """Open an audio run if the app is available and the preview is enabled."""
    if (client := hass.data.get(DATA_CLIENT)) is None:
        return None
    if not async_is_enabled(hass):
        return None
    had_info = client.info is not None
    run = await client.async_start_run(request, audio)
    if had_info and client.info is None:
        _async_wake_words_changed(hass)
    return run
