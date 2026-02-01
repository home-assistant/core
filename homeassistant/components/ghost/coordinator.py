"""DataUpdateCoordinator for Ghost."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from aioghost import GhostAdminAPI
from aioghost.exceptions import GhostAuthError, GhostError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import GhostConfigEntry

_LOGGER = logging.getLogger(__name__)


class GhostDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Ghost data."""

    config_entry: GhostConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: GhostAdminAPI,
        site_title: str,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.site_title = site_title

        super().__init__(
            hass,
            _LOGGER,
            name=f"Ghost ({site_title})",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Ghost API."""
        try:
            (
                site,
                posts,
                members,
                latest_post,
                latest_email,
                activitypub,
                mrr,
                comments,
                newsletters,
            ) = await asyncio.gather(
                self.api.get_site(),
                self.api.get_posts_count(),
                self.api.get_members_count(),
                self.api.get_latest_post(),
                self.api.get_latest_email(),
                self.api.get_activitypub_stats(),
                self.api.get_mrr(),
                self.api.get_comments_count(),
                self.api.get_newsletters(),
            )
        except GhostAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except GhostError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err

        return {
            "site": site,
            "posts": posts,
            "members": members,
            "latest_post": latest_post,
            "latest_email": latest_email,
            "activitypub": activitypub,
            "mrr": mrr,
            "comments": comments,
            "newsletters": newsletters,
        }
