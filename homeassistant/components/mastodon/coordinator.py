"""Define an object to manage fetching Mastodon data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from mastodon import Mastodon
from mastodon.Mastodon import Account, Instance, InstanceV2, MastodonError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


@dataclass
class MastodonData:
    """Mastodon data type."""

    client: Mastodon
    instance: InstanceV2 | Instance
    account: Account
    coordinator: MastodonCoordinator


type MastodonConfigEntry = ConfigEntry[MastodonData]


class MastodonCoordinator(DataUpdateCoordinator[Account]):
    """Class to manage fetching Mastodon data."""

    config_entry: MastodonConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: MastodonConfigEntry, client: Mastodon
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name="Mastodon",
            update_interval=timedelta(hours=1),
        )
        self.client = client

    async def _async_update_data(self) -> Account:
        try:
            account: Account = await self.hass.async_add_executor_job(
                self.client.account_verify_credentials
            )
        except MastodonError as ex:
            raise UpdateFailed(ex) from ex

        return account
