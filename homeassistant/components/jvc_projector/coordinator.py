"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from jvcprojector import (
    JvcProjector,
    JvcProjectorAuthError,
    JvcProjectorTimeoutError,
    command as cmd,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import INPUT, NAME, POWER

_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=10)
INTERVAL_FAST = timedelta(seconds=5)

type JVCConfigEntry = ConfigEntry[JvcProjectorDataUpdateCoordinator]


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the JVC Projector integration."""

    config_entry: JVCConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: JVCConfigEntry, device: JvcProjector
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=NAME,
            update_interval=INTERVAL_SLOW,
        )

        self.device: JvcProjector = device

        if TYPE_CHECKING:
            assert config_entry.unique_id is not None
        self.unique_id = config_entry.unique_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the latest state data."""
        state: dict[str, str | None] = {
            POWER: None,
            INPUT: None,
        }

        try:
            state[POWER] = await self.device.get(cmd.Power)

            if state[POWER] == cmd.Power.ON:
                state[INPUT] = await self.device.get(cmd.Input)

        except JvcProjectorTimeoutError as err:
            raise UpdateFailed(f"Unable to connect to {self.device.host}") from err
        except JvcProjectorAuthError as err:
            raise ConfigEntryAuthFailed("Password authentication failed") from err

        if state[POWER] != cmd.Power.STANDBY:
            self.update_interval = INTERVAL_FAST
        else:
            self.update_interval = INTERVAL_SLOW

        return state
