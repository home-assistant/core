"""The Immich Frames integration."""

from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .cache import FrameCache
from .const import (
    CONF_ALBUM_IDS,
    CONF_FRAME_ID,
    CONF_IMMICH_ENTRY_ID,
    CONF_MIGRATION_REQUIRED,
    CONF_MODE,
    CONF_ORIENTATION,
    CONF_PAIR_WINDOW,
    CONF_PHOTO_FIT,
    CONF_SCREEN_SHAPE,
    CONF_SMART_QUERY,
    CONF_SOURCE,
    CONF_TIME_RANGE,
    DEFAULT_SOURCE,
    DOMAIN,
)
from .coordinator import ImmichFramesConfigEntry, ImmichFramesDataUpdateCoordinator

PLATFORMS = [Platform.IMAGE]
CONFIG_SCHEMA = cv.config_entry_only_config_schema("immich_frames")
OPTION_KEYS = frozenset(
    {
        CONF_ALBUM_IDS,
        CONF_MODE,
        CONF_ORIENTATION,
        CONF_PAIR_WINDOW,
        CONF_PHOTO_FIT,
        CONF_SCREEN_SHAPE,
        CONF_SMART_QUERY,
        CONF_SOURCE,
        CONF_TIME_RANGE,
    }
)
LEGACY_URL = "url"
LEGACY_SOURCE_OPTIONS = frozenset({"all", "album", "smart"})


def _endpoint_parts(url: str) -> tuple[bool, str, int] | None:
    """Return the comparable endpoint parts from a legacy URL."""
    parsed = urlsplit(url if "://" in url else f"http://{url}")
    if parsed.hostname is None:
        return None
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError:
        return None
    return parsed.scheme.lower() == "https", parsed.hostname.casefold(), port


def _parent_endpoint(entry: object) -> tuple[bool, str, int] | None:
    """Return the comparable endpoint parts from a Core Immich entry."""
    data = getattr(entry, "data", {})
    host = str(data.get(CONF_HOST, "")).strip()
    if not host:
        return None
    try:
        port = int(data.get(CONF_PORT, 443 if data.get(CONF_SSL) else 80))
    except TypeError, ValueError:
        return None
    return bool(data.get(CONF_SSL)), host.casefold(), port


def _legacy_options(data: dict[str, object]) -> dict[str, object]:
    """Translate the settings stored by the released HACS integration."""
    source = str(data.get(CONF_SOURCE, DEFAULT_SOURCE))
    if source not in LEGACY_SOURCE_OPTIONS:
        source = DEFAULT_SOURCE
    options = {
        key: data[key] for key in OPTION_KEYS if key in data and key != CONF_ALBUM_IDS
    }
    options[CONF_SOURCE] = source
    if CONF_ALBUM_IDS not in options and data.get("album_id"):
        options[CONF_ALBUM_IDS] = [data["album_id"]]
    return options


def _migrate_legacy_entry(hass: HomeAssistant, entry: ImmichFramesConfigEntry) -> None:
    """Bind a released HACS entry to a matching Core Immich account."""
    legacy_data = dict(entry.data)
    legacy_url = str(legacy_data.get(LEGACY_URL, "")).strip()
    legacy_api_key = str(legacy_data.get(CONF_API_KEY, ""))
    legacy_source = str(legacy_data.get(CONF_SOURCE, DEFAULT_SOURCE))
    legacy_endpoint = _endpoint_parts(legacy_url)
    options = _legacy_options(legacy_data)
    matches = [
        parent
        for parent in hass.config_entries.async_entries("immich")
        if _parent_endpoint(parent) == legacy_endpoint
        and str(parent.data.get(CONF_API_KEY, "")) == legacy_api_key
    ]
    if len(matches) == 1 and legacy_source in LEGACY_SOURCE_OPTIONS:
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_IMMICH_ENTRY_ID: matches[0].entry_id,
                CONF_FRAME_ID: entry.entry_id,
            },
            options=options,
            version=4,
        )
        return

    # Remove the legacy credential from the frame entry. Reconfigure lets the
    # user choose the Core Immich account when an exact match is not possible.
    hass.config_entries.async_update_entry(
        entry,
        data={
            CONF_FRAME_ID: entry.entry_id,
            CONF_MIGRATION_REQUIRED: True,
        },
        options=options,
        version=4,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Immich Frames integration."""
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Migrate an older frame entry to the current source model."""
    if CONF_IMMICH_ENTRY_ID not in entry.data and entry.data.get(LEGACY_URL):
        _migrate_legacy_entry(hass, entry)
        return True
    if entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_SOURCE: entry.data.get(CONF_SOURCE, DEFAULT_SOURCE),
            },
            version=2,
        )
    if entry.version < 3:
        moved_options = {
            key: value
            for key, value in entry.data.items()
            if key in OPTION_KEYS and key not in entry.options
        }
        hass.config_entries.async_update_entry(
            entry,
            data={
                key: value
                for key, value in entry.data.items()
                if key not in OPTION_KEYS
            },
            options={**moved_options, **entry.options},
            version=3,
        )
    if entry.version < 4:
        hass.config_entries.async_update_entry(entry, version=4)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Set up an Immich frame."""
    if entry.data.get(CONF_MIGRATION_REQUIRED):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="migration_required",
        )
    immich_entry = hass.config_entries.async_get_entry(entry.data[CONF_IMMICH_ENTRY_ID])
    if immich_entry is None or immich_entry.state is not ConfigEntryState.LOADED:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="immich_not_ready",
        )
    try:
        coordinator = ImmichFramesDataUpdateCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        if err.translation_key != "no_photos":
            raise
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> bool:
    """Unload an Immich frame without closing the shared Immich client."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: ImmichFramesConfigEntry
) -> None:
    """Remove the private cached image for a deleted frame."""
    cache = FrameCache(
        Path(hass.config.path(".storage", f"immich_frames_{entry.entry_id}.json"))
    )
    await hass.async_add_executor_job(cache.clear)
