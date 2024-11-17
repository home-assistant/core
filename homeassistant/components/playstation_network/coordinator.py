"""Coordinator for the Playstation Network Integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlaystationNetworkData:
    """Dataclass representing data retrieved from the Playstation Network api."""

    presence: dict
    username: str
    account_id: str
    available: bool
    title_metadata: dict
    platform: dict


class PlaystationNetworkCoordinator(DataUpdateCoordinator[PlaystationNetworkData]):
    """Data update coordinator for PSN."""

    def __init__(self, hass: HomeAssistant, user) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )

        self.user = user
        self.psn: PlaystationNetworkData = PlaystationNetworkData(
            {}, "", "", False, {}, {}
        )

    async def _async_update_data(self) -> PlaystationNetworkData:
        """Get the latest data from the PSN."""
        try:
            self.psn.username = self.user.online_id
            self.psn.account_id = self.user.account_id
            self.psn.presence = await self.hass.async_add_executor_job(
                self.user.get_presence
            )

            self.psn.available = (
                self.psn.presence.get("basicPresence", {}).get("availability")
                == "availableToPlay"
            )
            self.psn.platform = self.psn.presence.get("basicPresence", {}).get(
                "primaryPlatformInfo"
            )
            game_title_info_list = self.psn.presence.get("basicPresence", {}).get(
                "gameTitleInfoList"
            )

            if game_title_info_list:
                self.psn.title_metadata = game_title_info_list[0]

        except PSNAWPAuthenticationError as error:
            raise UpdateFailed(error) from error

        return self.psn
