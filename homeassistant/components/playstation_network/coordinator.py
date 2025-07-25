"""Coordinator for the PlayStation Network Integration."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
import logging

from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPClientError,
    PSNAWPServerError,
)
from psnawp_api.models.trophies import TrophyTitle

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
            lambda: list(self.psn.user.trophy_titles())
        )
        await self.config_entry.runtime_data.user_data.async_request_refresh()
        return self.psn.trophy_titles
