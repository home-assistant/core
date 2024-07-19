"""Define an object to manage fetching Mastodon data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import MastodonError, MastodonUnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


@dataclass
class MastodonData:
    """Mastodon data type."""

    client: Mastodon
    coordinator: MastodonCoordinator


type MastodonConfigEntry = ConfigEntry[MastodonData]


class MastodonCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Mastodon data."""

    config_entry: MastodonConfigEntry

    def __init__(self, hass: HomeAssistant, client: Mastodon) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, logger=LOGGER, name="Mastodon", update_interval=timedelta(hours=1)
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            account: dict = await self.hass.async_add_executor_job(
                self.client.account_verify_credentials
            )
        except MastodonUnauthorizedError as ex:
            raise ConfigEntryAuthFailed from ex
        except MastodonError as ex:
            raise UpdateFailed(ex) from ex

        return account
