"""Coordinator for Immich Frames."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from aioimmich import Immich
from aioimmich.assets.models import ImmichAsset
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_IMMICH_ENTRY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ImmichFramesData:
    """Data for the currently displayed asset."""

    asset: ImmichAsset
    image: bytes
    updated_at: datetime


type ImmichFramesConfigEntry = ConfigEntry[ImmichFramesDataUpdateCoordinator]


class ImmichFramesDataUpdateCoordinator(DataUpdateCoordinator[ImmichFramesData]):
    """Fetch the latest image through the configured Immich integration."""

    config_entry: ImmichFramesConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ImmichFramesConfigEntry) -> None:
        """Initialize the frame coordinator."""
        self.config_entry = entry
        immich_entry = hass.config_entries.async_get_entry(
            entry.data[CONF_IMMICH_ENTRY_ID]
        )
        if immich_entry is None or not getattr(immich_entry, "runtime_data", None):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="immich_not_ready",
            )
        self.immich_entry = immich_entry
        self.api: Immich = immich_entry.runtime_data.api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    @override
    async def _async_update_data(self) -> ImmichFramesData:
        """Fetch one image from the existing Immich account."""
        try:
            assets = await self.api.search.async_get_all(
                page_size=100,
                max_pages=20,
            )
            eligible = [
                asset
                for asset in assets
                if not asset.is_trashed
                and not asset.is_offline
                and asset.asset_type.value == "IMAGE"
            ]
            if not eligible:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_photos",
                )
            asset = max(eligible, key=lambda item: item.local_datetime)
            image = await self.api.assets.async_view_asset(
                asset.asset_id, size="preview"
            )
        except ImmichUnauthorizedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain="immich",
                translation_key="auth_error",
            ) from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        return ImmichFramesData(asset, image, datetime.now().astimezone())
