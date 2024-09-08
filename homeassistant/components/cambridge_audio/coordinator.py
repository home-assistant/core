"""Define an object to manage fetching Cambridge Audio data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from aiostreammagic import (
    Info,
    PlayState,
    Source,
    State,
    StreamMagicClient,
    StreamMagicError,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


@dataclass
class CambridgeAudioData:
    """Class for Cambridge Audio data."""

    info: Info
    sources: list[Source]
    state: State
    play_state: PlayState


class CambridgeAudioCoordinator(DataUpdateCoordinator[CambridgeAudioData]):
    """Class to manage fetching Cambridge Audio data."""

    def __init__(self, hass: HomeAssistant, client: StreamMagicClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"Cambridge Audio {client.host}",
            update_interval=timedelta(seconds=15),
        )
        self.client = client

    async def _async_update_data(self) -> CambridgeAudioData:
        try:
            info = await self.client.get_info()
            sources = await self.client.get_sources()
            state = await self.client.get_state()
            play_state = await self.client.get_play_state()
        except StreamMagicError as error:
            raise UpdateFailed(error) from error
        else:
            return CambridgeAudioData(info, sources, state, play_state)
