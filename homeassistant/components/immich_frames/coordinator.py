"""Coordinator for Immich Frames."""

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import hashlib
import logging
from pathlib import Path
from typing import Any, override

from aioimmich import Immich
from aioimmich.assets.models import ImmichAsset
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichError, ImmichUnauthorizedError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .cache import FrameCache
from .const import (
    CONF_IMMICH_ENTRY_ID,
    CONF_MODE,
    CONF_PHOTO_FIT,
    CONF_SCREEN_SHAPE,
    DEFAULT_MODE,
    DEFAULT_PHOTO_FIT,
    DOMAIN,
    MODE_PAIRS_ONLY,
    screen_shape,
)
from .rendering import render
from .selection import (
    UnsupportedSourceError,
    async_get_candidates,
    candidates_with_companion,
    choose_asset,
    selected_photos,
)

_LOGGER = logging.getLogger(__name__)
RECENT_HISTORY_LIMIT = 20
CANDIDATE_CACHE_INTERVAL = timedelta(minutes=5)


@dataclass
class ImmichFramesData:
    """Data for the currently rendered frame."""

    asset: ImmichAsset
    image: bytes
    updated_at: datetime
    photos: tuple[ImmichAsset, ...] = ()
    matching_assets: int = 0
    connected: bool = True
    using_cache: bool = False
    status: str = "ready"


type ImmichFramesConfigEntry = ConfigEntry[ImmichFramesDataUpdateCoordinator]


class ImmichFramesDataUpdateCoordinator(DataUpdateCoordinator[ImmichFramesData]):
    """Select, render, cache, and rotate photos through the parent Immich entry."""

    config_entry: ImmichFramesConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ImmichFramesConfigEntry) -> None:
        """Initialize the frame coordinator."""
        self.config_entry = entry
        self.options: dict[str, Any] = {**entry.data, **entry.options}
        immich_entry = hass.config_entries.async_get_entry(
            self.options[CONF_IMMICH_ENTRY_ID]
        )
        if (
            immich_entry is None
            or immich_entry.state is not ConfigEntryState.LOADED
            or not getattr(immich_entry, "runtime_data", None)
        ):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="immich_not_ready",
            )
        self.immich_entry = immich_entry
        self.api: Immich = immich_entry.runtime_data.api
        self._parent_identity_value = self._parent_identity(immich_entry)
        self.paused = False
        self._connected: bool | None = None
        self._recent_ids: set[str] = set()
        self._recent_order: deque[str] = deque()
        self._candidate_cache: list[ImmichAsset] | None = None
        self._candidate_cache_updated_at: datetime | None = None
        self._account_state_invalidated = False
        self._cache = FrameCache(
            Path(hass.config.path(".storage", f"immich_frames_{entry.entry_id}.json"))
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @override
    async def _async_setup(self) -> None:
        """Load a verified cached frame before the first network refresh."""
        cached = await self.hass.async_add_executor_job(
            self._cache.read,
            self.options,
            self.immich_entry.entry_id,
            self._parent_identity_value,
        )
        if cached is not None:
            asset, image, rendered_at = cached
            self.data = ImmichFramesData(
                asset=asset,
                image=image,
                updated_at=rendered_at,
                photos=(asset,),
                connected=False,
                using_cache=True,
                status="cached",
            )
            self._remember_assets((asset,))

    @override
    async def _async_update_data(self) -> ImmichFramesData:
        """Fetch, render, and cache the next frame."""
        if self.paused and self.data is not None:
            return self.data
        if not self._refresh_parent():
            return self._cached_or_raise(
                "immich_not_ready",
                RuntimeError("The parent Immich entry is not ready"),
                status="parent_not_ready",
                connection_failed=True,
            )

        try:
            candidates = await self._async_get_candidates()
            if not candidates:
                return self._cached_or_raise(
                    "no_photos", LookupError("no photos"), status="no_matching_photos"
                )
            selection_candidates = candidates
            if str(self.options.get(CONF_MODE, DEFAULT_MODE)) == MODE_PAIRS_ONLY:
                selection_candidates = candidates_with_companion(
                    candidates, self.options
                )
            self._reset_recent_if_exhausted(selection_candidates)
            primary = choose_asset(selection_candidates, self.options, self._recent_ids)
            photos = selected_photos(primary, candidates, self.options)
            payloads = [
                await self.api.assets.async_view_asset(asset.asset_id, size="preview")
                for asset in photos
            ]
            fit = str(self.options.get(CONF_PHOTO_FIT, DEFAULT_PHOTO_FIT))
            image, _layout = await self.hass.async_add_executor_job(
                render,
                payloads,
                screen_shape(self.options.get(CONF_SCREEN_SHAPE)),
                fit,
            )
        except ImmichUnauthorizedError as err:
            self.immich_entry.async_start_reauth(self.hass)
            return self._cached_or_raise(
                "cannot_connect",
                err,
                status="authentication_required",
                connection_failed=True,
            )
        except ImmichError as err:
            return self._cached_or_raise("upstream_error", err, status="upstream_error")
        except CONNECT_ERRORS as err:
            return self._cached_or_raise(
                "cannot_connect",
                err,
                status="upstream_unavailable",
                connection_failed=True,
            )
        except UnsupportedSourceError as err:
            return self._cached_or_raise(
                "unsupported_source", err, status="unsupported"
            )
        except LookupError as err:
            return self._cached_or_raise("no_photos", err, status="no_matching_photos")
        except (OSError, ValueError) as err:
            return self._cached_or_raise("invalid_image", err, status="invalid_image")

        result = ImmichFramesData(
            asset=photos[0],
            image=image,
            updated_at=dt_util.utcnow(),
            photos=photos,
            matching_assets=len(candidates),
            connected=True,
            status="ready",
        )
        self._account_state_invalidated = False
        if self._connected is False:
            _LOGGER.info("Immich connection restored for %s", self.config_entry.title)
        self._connected = True
        self._remember_assets(photos)
        try:
            await self.hass.async_add_executor_job(
                self._cache.write,
                result.asset,
                result.image,
                self.options,
                self.immich_entry.entry_id,
                self._parent_identity_value,
                result.updated_at,
            )
        except OSError, ValueError:
            _LOGGER.warning("Could not save the Immich Frames cache", exc_info=True)
        return result

    def _refresh_parent(self) -> bool:
        """Refresh the parent entry and client after a parent reload."""
        immich_entry = self.hass.config_entries.async_get_entry(
            self.options[CONF_IMMICH_ENTRY_ID]
        )
        if (
            immich_entry is None
            or immich_entry.state is not ConfigEntryState.LOADED
            or not getattr(immich_entry, "runtime_data", None)
        ):
            return False
        parent_identity = self._parent_identity(immich_entry)
        if parent_identity != self._parent_identity_value:
            self._invalidate_candidate_cache()
            self._recent_ids.clear()
            self._recent_order.clear()
            self._account_state_invalidated = True
            self._connected = None
            self._parent_identity_value = parent_identity
        self.immich_entry = immich_entry
        self.api = immich_entry.runtime_data.api
        return True

    async def _async_get_candidates(self) -> list[ImmichAsset]:
        """Return candidates, refreshing the bounded index when it expires."""
        now = dt_util.utcnow()
        if (
            self._candidate_cache is not None
            and self._candidate_cache_updated_at is not None
            and now - self._candidate_cache_updated_at < CANDIDATE_CACHE_INTERVAL
        ):
            return self._candidate_cache
        candidates = await async_get_candidates(self.api, self.options, now)
        self._candidate_cache = candidates
        self._candidate_cache_updated_at = now
        return candidates

    def _invalidate_candidate_cache(self) -> None:
        """Force the next update to retrieve the current candidate set."""
        self._candidate_cache = None
        self._candidate_cache_updated_at = None

    def _parent_identity(self, entry: ConfigEntry | None = None) -> str:
        """Return a non-secret identity for the configured Immich account."""
        parent_entry = entry or self.immich_entry
        endpoint = str(parent_entry.runtime_data.configuration_url)
        key_fingerprint = hashlib.sha256(
            str(parent_entry.data.get(CONF_API_KEY, "")).encode()
        ).hexdigest()
        return f"{endpoint}|{key_fingerprint}"

    def _remember_assets(self, assets: tuple[ImmichAsset, ...]) -> None:
        """Remember a bounded set of recently displayed assets."""
        for asset in assets:
            asset_id = asset.asset_id
            if asset_id in self._recent_ids:
                continue
            if len(self._recent_order) >= RECENT_HISTORY_LIMIT:
                self._recent_ids.discard(self._recent_order.popleft())
            self._recent_order.append(asset_id)
            self._recent_ids.add(asset_id)

    def _reset_recent_if_exhausted(self, candidates: list[ImmichAsset]) -> None:
        """Reset recent history when every candidate has been displayed."""
        candidate_ids = {asset.asset_id for asset in candidates}
        if not candidate_ids or not candidate_ids.issubset(self._recent_ids):
            return
        self._recent_ids.clear()
        self._recent_order.clear()
        if self.data is not None and not self._account_state_invalidated:
            self._remember_assets(self.data.photos or (self.data.asset,))

    def _cached_or_raise(
        self,
        translation_key: str,
        error: Exception,
        *,
        status: str,
        connection_failed: bool = False,
    ) -> ImmichFramesData:
        """Use the last rendered image when a recoverable update fails."""
        if self.data is not None:
            if connection_failed and self._connected is not False:
                _LOGGER.info("Immich is unavailable for %s", self.config_entry.title)
            if connection_failed:
                self._connected = False
            return replace(
                self.data,
                connected=not connection_failed,
                using_cache=True,
                status=status,
            )
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key=translation_key,
        ) from error

    @staticmethod
    def _orientation_is_portrait(asset: ImmichAsset) -> bool:
        """Return whether EXIF dimensions identify a portrait."""
        exif = asset.exif_info
        return bool(
            exif
            and exif.exif_image_width
            and exif.exif_image_height
            and exif.exif_image_height > exif.exif_image_width
        )

    @callback
    def async_update_settings(self, changes: dict[str, Any]) -> None:
        """Update frame options and request a clean reload."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, **changes},
        )
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def async_refresh_now(self) -> None:
        """Refresh immediately."""
        paused = self.paused
        self.paused = False
        self._invalidate_candidate_cache()
        try:
            await self.async_refresh()
        finally:
            self.paused = paused

    async def async_next(self) -> None:
        """Advance to another photo."""
        self.paused = False
        await self.async_refresh()

    async def async_clear_cache(self) -> None:
        """Clear the persistent image cache."""
        await self.hass.async_add_executor_job(self._cache.clear)
