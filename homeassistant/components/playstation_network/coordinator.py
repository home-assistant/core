"""Coordinator for the PlayStation Network Integration."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPClientError,
    PSNAWPError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
)
from psnawp_api.models import User
from psnawp_api.models.group.group_datatypes import GroupDetails
from psnawp_api.models.trophies import TrophyTitle

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .helpers import PlaystationNetwork, PlaystationNetworkData

_LOGGER = logging.getLogger(__name__)

type PlaystationNetworkConfigEntry = ConfigEntry[PlaystationNetworkRuntimeData]


@dataclass
class PlaystationNetworkRuntimeData:
    """Dataclass holding PSN runtime data."""

    user_data: PlaystationNetworkUserDataCoordinator
    trophy_titles: PlaystationNetworkTrophyTitlesCoordinator
    groups: PlaystationNetworkGroupsUpdateCoordinator
    friends: dict[str, PlaystationNetworkFriendDataCoordinator]


class PlayStationNetworkBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator for PSN."""

    config_entry: PlaystationNetworkConfigEntry
    _update_inverval: timedelta

    def __init__(
        self,
        hass: HomeAssistant,
        psn: PlaystationNetwork,
        config_entry: PlaystationNetworkConfigEntry,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            config_entry=config_entry,
            update_interval=self._update_interval,
        )

        self.psn = psn

    @abstractmethod
    async def update_data(self) -> _DataT:
        """Update coordinator data."""

    async def _async_update_data(self) -> _DataT:
        """Get the latest data from the PSN."""
        try:
            return await self.update_data()
        except PSNAWPAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="not_ready",
            ) from error
        except (PSNAWPServerError, PSNAWPClientError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from error


class PlaystationNetworkUserDataCoordinator(
    PlayStationNetworkBaseCoordinator[PlaystationNetworkData]
):
    """Data update coordinator for PSN."""

    _update_interval = timedelta(seconds=30)

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            await self.psn.async_setup()
        except PSNAWPAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="not_ready",
            ) from error
        except (PSNAWPServerError, PSNAWPClientError) as error:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from error

    async def update_data(self) -> PlaystationNetworkData:
        """Get the latest data from the PSN."""
        return await self.psn.get_data()


class PlaystationNetworkTrophyTitlesCoordinator(
    PlayStationNetworkBaseCoordinator[list[TrophyTitle]]
):
    """Trophy titles data update coordinator for PSN."""

    _update_interval = timedelta(days=1)

    async def update_data(self) -> list[TrophyTitle]:
        """Update trophy titles data."""
        self.psn.trophy_titles = await self.hass.async_add_executor_job(
            lambda: list(self.psn.user.trophy_titles(page_size=500))
        )
        await self.config_entry.runtime_data.user_data.async_request_refresh()
        return self.psn.trophy_titles


class PlaystationNetworkGroupsUpdateCoordinator(
    PlayStationNetworkBaseCoordinator[dict[str, GroupDetails]]
):
    """Groups data update coordinator for PSN."""

    _update_interval = timedelta(hours=3)

    async def update_data(self) -> dict[str, GroupDetails]:
        """Update groups data."""
        return await self.hass.async_add_executor_job(
            lambda: {
                group_info.group_id: group_info.get_group_information()
                for group_info in self.psn.client.get_groups()
                if not group_info.group_id.startswith("~")
            }
        )


class PlaystationNetworkFriendDataCoordinator(
    PlayStationNetworkBaseCoordinator[PlaystationNetworkData]
):
    """Friend status data update coordinator for PSN."""

    user: User
    profile: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        psn: PlaystationNetwork,
        config_entry: PlaystationNetworkConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the Coordinator."""
        self._update_interval = timedelta(
            seconds=max(9 * len(config_entry.subentries), 180)
        )
        super().__init__(hass, psn, config_entry)
        self.subentry = subentry

    def _setup(self) -> None:
        """Set up the coordinator."""
        if TYPE_CHECKING:
            assert self.subentry.unique_id
        self.user = self.psn.psn.user(account_id=self.subentry.unique_id)
        self.profile = self.user.profile()

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            await self.hass.async_add_executor_job(self._setup)
        except PSNAWPNotFoundError as error:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="user_not_found",
                translation_placeholders={"user": self.subentry.title},
            ) from error

        except PSNAWPAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="not_ready",
            ) from error

        except (PSNAWPServerError, PSNAWPClientError) as error:
            _LOGGER.debug("Update failed", exc_info=True)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from error

    def _update_data(self) -> PlaystationNetworkData:
        """Update friend status data."""
        try:
            return PlaystationNetworkData(
                username=self.user.online_id,
                account_id=self.user.account_id,
                presence=self.user.get_presence(),
                profile=self.profile,
            )
        except PSNAWPForbiddenError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="user_profile_private",
                translation_placeholders={"user": self.subentry.title},
            ) from error
        except PSNAWPError:
            raise

    async def update_data(self) -> PlaystationNetworkData:
        """Update friend status data."""
        return await self.hass.async_add_executor_job(self._update_data)
