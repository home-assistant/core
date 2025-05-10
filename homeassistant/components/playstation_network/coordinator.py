"""Coordinator for the PlayStation Network Integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPServerError,
)
from psnawp_api.models.user import User

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .helpers import PlaystationNetwork, PlaystationNetworkData

_LOGGER = logging.getLogger(__name__)

type PlaystationNetworkConfigEntry = ConfigEntry[PlaystationNetworkCoordinator]


class PlaystationNetworkCoordinator(DataUpdateCoordinator[PlaystationNetworkData]):
    """Data update coordinator for PSN."""

    config_entry: PlaystationNetworkConfigEntry
    user: User

    def __init__(self, hass: HomeAssistant, psn: PlaystationNetwork) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=timedelta(seconds=30),
        )

        self.psn = psn

    async def _async_update_data(self) -> PlaystationNetworkData:
        """Get the latest data from the PSN."""
        try:
            return await self.hass.async_add_executor_job(self.psn.get_data)
        except (PSNAWPAuthenticationError, PSNAWPServerError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from error

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            self.user = await self.hass.async_add_executor_job(self.psn.get_user)
        except PSNAWPAuthenticationError as error:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="not_ready",
            ) from error
