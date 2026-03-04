"""DataUpdateCoordinator for Ghost."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
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


@dataclass
class GhostData:
    """Data returned by the Ghost coordinator."""

    site: dict[str, Any]
    posts: dict[str, Any]
    members: dict[str, Any]
    latest_post: dict[str, Any] | None
    latest_email: dict[str, Any] | None
    activitypub: dict[str, Any]
    mrr: dict[str, Any]
    arr: dict[str, Any]
    comments: int
    newsletters: dict[str, dict[str, Any]]


class GhostDataUpdateCoordinator(DataUpdateCoordinator[GhostData]):
    """Class to manage fetching Ghost data."""

    config_entry: GhostConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: GhostAdminAPI,
        config_entry: GhostConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=f"Ghost ({config_entry.title})",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> GhostData:
        """Fetch data from Ghost API."""
        try:
            (site, posts, members, latest_post, latest_email) = await asyncio.gather(
                self.api.get_site(),
                self.api.get_posts_count(),
                self.api.get_members_count(),
                self.api.get_latest_post(),
                self.api.get_latest_email(),
            )
            (activitypub, mrr, arr, comments, newsletters) = await asyncio.gather(
                self.api.get_activitypub_stats(),
                self.api.get_mrr(),
                self.api.get_arr(),
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

        return GhostData(
            site=site,
            posts=posts,
            members=members,
            latest_post=latest_post,
            latest_email=latest_email,
            activitypub=activitypub,
            mrr=mrr,
            arr=arr,
            comments=comments,
            newsletters={n["id"]: n for n in newsletters if "id" in n},
        )
