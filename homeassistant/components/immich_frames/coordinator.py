"""Coordinator for Immich Frames."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any, override

from aioimmich import Immich
from aioimmich.assets.models import ImmichAsset
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .cache import FrameCache
from .const import (
    CONF_IMMICH_ENTRY_ID,
    CONF_INTERVAL,
    CONF_MODE,
    CONF_PHOTO_FIT,
    CONF_SCREEN_SHAPE,
    DEFAULT_INTERVAL,
    DEFAULT_MODE,
    DEFAULT_PHOTO_FIT,
    DOMAIN,
    MODE_PAIRS,
    PHOTO_FIT_FULL,
    screen_shape,
)
from .rendering import render
from .selection import (
    UnsupportedSourceError,
    async_get_candidates,
    choose_asset,
    selected_photos,
)

_LOGGER = logging.getLogger(__name__)


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
        if immich_entry is None or not getattr(immich_entry, "runtime_data", None):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="immich_not_ready",
            )
        self.immich_entry = immich_entry
        self.api: Immich = immich_entry.runtime_data.api
        self.paused = False
        self._connected: bool | None = None
        self._recent_ids: set[str] = set()
        self._history: list[ImmichFramesData] = []
        self._cache = FrameCache(
            Path(hass.config.path(".storage", f"immich_frames_{entry.entry_id}.json"))
        )
        interval = max(
            10, min(86400, int(self.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)))
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    @override
    async def _async_setup(self) -> None:
        """Load a verified cached frame before the first network refresh."""
        cached = await self.hass.async_add_executor_job(
            self._cache.read,
            self.options,
            self.immich_entry.entry_id,
        )
        if cached is not None:
            asset, image = cached
            self.data = ImmichFramesData(
                asset=asset,
                image=image,
                updated_at=dt_util.utcnow(),
                photos=(asset,),
                connected=False,
                using_cache=True,
                status="cached",
            )
            self._history.append(self.data)
            self._recent_ids.add(asset.asset_id)

    @override
    async def _async_update_data(self) -> ImmichFramesData:
        """Fetch, render, and cache the next frame."""
        if self.paused and self.data is not None:
            return self.data

        try:
            candidates = await async_get_candidates(
                self.api, self.options, dt_util.utcnow()
            )
            if not candidates:
                return self._cached_or_raise(
                    "no_photos", LookupError("no photos"), status="no_matching_photos"
                )
            primary = choose_asset(candidates, self.options, self._recent_ids)
            photos = selected_photos(primary, candidates, self.options)
            payloads = [
                await self.api.assets.async_view_asset(asset.asset_id, size="preview")
                for asset in photos
            ]
            fit = str(self.options.get(CONF_PHOTO_FIT, DEFAULT_PHOTO_FIT))
            if (
                len(photos) == 1
                and str(self.options.get(CONF_MODE, DEFAULT_MODE)) == MODE_PAIRS
                and self._orientation_is_portrait(primary)
            ):
                fit = PHOTO_FIT_FULL
            image, _layout = await self.hass.async_add_executor_job(
                render,
                payloads,
                screen_shape(self.options.get(CONF_SCREEN_SHAPE)),
                fit,
            )
        except ImmichUnauthorizedError as err:
            self._connected = False
            raise ConfigEntryAuthFailed(
                translation_domain="immich",
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            return self._cached_or_raise(
                "cannot_connect", err, status="upstream_unavailable"
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
        if self._connected is False:
            _LOGGER.info("Immich connection restored for %s", self.config_entry.title)
        self._connected = True
        self._recent_ids.update(asset.asset_id for asset in photos)
        self._history.append(result)
        del self._history[:-20]
        try:
            await self.hass.async_add_executor_job(
                self._cache.write,
                result.asset,
                result.image,
                self.options,
                self.immich_entry.entry_id,
            )
        except (OSError, ValueError):
            _LOGGER.warning("Could not save the Immich Frames cache", exc_info=True)
        return result

    def _cached_or_raise(
        self,
        translation_key: str,
        error: Exception,
        *,
        status: str,
    ) -> ImmichFramesData:
        """Use the last rendered image when a recoverable update fails."""
        if self.data is not None:
            if self._connected is not False:
                _LOGGER.warning("Immich is unavailable for %s", self.config_entry.title)
            self._connected = False
            return replace(
                self.data,
                connected=False,
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
        await self.async_refresh()

    async def async_next(self) -> None:
        """Advance to another photo."""
        self.paused = False
        await self.async_refresh()

    async def async_previous(self) -> None:
        """Return to the previous rendered photo."""
        if len(self._history) > 1:
            self._history.pop()
            self.async_set_updated_data(self._history[-1])

    async def async_clear_cache(self) -> None:
        """Clear the persistent image cache."""
        await self.hass.async_add_executor_job(self._cache.clear)
