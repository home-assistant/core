"""Define an object to manage fetching Mastodon data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import MastodonError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


class MastodonCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Mastodon data."""

    def __init__(self, hass: HomeAssistant, client: Mastodon) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, logger=LOGGER, name="Mastodon", update_interval=timedelta(hours=1)
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            account: dict = await self.hass.async_add_executor_job(
                self.client.account_verify_credentials
            )
        except MastodonError as ex:
            raise UpdateFailed(ex) from ex

        return account
