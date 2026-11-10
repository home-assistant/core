"""The Voice support integration.

Loading this integration means a satellite exists: that is when the app it
provides is wanted, so setup puts the app in place. Depend on it only from
a component that is itself only there for satellites.

This is an internal component. What it exports is for Home Assistant's own
voice components; other integrations, custom ones above all, must not use
any of it, and it can change in any release.
"""

from collections.abc import AsyncIterable
import logging

from homeassistant.components.hassio import AddonError
from homeassistant.components.labs import (
    EventLabsUpdatedData,
    async_is_preview_feature_enabled,
    async_subscribe_preview_feature,
)
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .app import get_app_manager
from .client import (
    API_VERSION,
    CONNECT_ERRORS,
    AudioRun,
    AudioRunRequest,
    UnsupportedVersionError,
    VoiceSupportClient,
    WakeWordAccepted,
    WakeWordRejected,
)
from .const import CONF_INTEGRATION_CREATED_APP, DOMAIN

# Internal, see the module docstring: not for other integrations to use
__all__ = [
    "DOMAIN",
    "SIGNAL_WAKE_WORDS_CHANGED",
    "AudioRun",
    "AudioRunRequest",
    "WakeWordAccepted",
    "WakeWordRejected",
    "async_start_run",
    "async_verifies_wake_word",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PREVIEW_FEATURE_WAKE_WORD_VERIFICATION = "wake_word_verification"

DATA_CLIENT: HassKey[VoiceSupportClient] = HassKey(DOMAIN)

SIGNAL_WAKE_WORDS_CHANGED = f"{DOMAIN}_wake_words_changed"
"""Sent when async_verifies_wake_word may answer differently than it did.

A satellite asked for wake word audio buffers it and detects at a lower
threshold, so it is told once rather than per detection -- which means it
has to be told again when the answer moves: the app arriving or going
away, or the person turning the preview feature off. Not when an app
update changes the models it has, which would need the client to say so
and is the rarest of the three by a long way.
"""

_LOGGER = logging.getLogger(__name__)


@callback
def async_is_enabled(hass: HomeAssistant) -> bool:
    """Whether the person has turned voice support on."""
    return async_is_preview_feature_enabled(
        hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION
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
def _async_wake_words_changed(hass: HomeAssistant) -> None:
    """Tell satellites the answer may have moved."""
    async_dispatcher_send(hass, SIGNAL_WAKE_WORDS_CHANGED)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up voice support."""

    async def _async_preview_feature_updated(event_data: EventLabsUpdatedData) -> None:
        if event_data["enabled"]:
            _async_provision(hass)
        _async_wake_words_changed(hass)

    async_subscribe_preview_feature(
        hass,
        DOMAIN,
        PREVIEW_FEATURE_WAKE_WORD_VERIFICATION,
        _async_preview_feature_updated,
    )
    _async_provision(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Connect to the app at the entry's address."""
    client = VoiceSupportClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        await client.async_connect()
    except CONNECT_ERRORS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"url": str(client.url)},
        ) from err
    except UnsupportedVersionError as err:
        # Not ready rather than an error: the app may get updated any time
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

    hass.data[DATA_CLIENT] = client
    _async_wake_words_changed(hass)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload the entry."""
    hass.data.pop(DATA_CLIENT).async_close()
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
    """Open a run with the app over this audio, or None to go on without one.

    None is not a failure: there is no app to ask right now, or voice
    support is turned off.
    """
    if (client := hass.data.get(DATA_CLIENT)) is None:
        return None
    if not async_is_enabled(hass):
        return None
    return await client.async_start_run(request, audio)
