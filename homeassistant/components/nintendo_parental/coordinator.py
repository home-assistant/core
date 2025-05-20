"""Nintendo Parental Controls data coordinator."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging

from pynintendoparental import Authenticator, NintendoParental
from pynintendoparental.exceptions import (
    InvalidOAuthConfigurationException,
    InvalidSessionTokenException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type NintendoParentalConfigEntry = ConfigEntry[NintendoUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=60)


class NintendoUpdateCoordinator(DataUpdateCoordinator):
    """Nintendo data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        authenticator: Authenticator,
        config_entry: NintendoParentalConfigEntry,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = NintendoParental(
            authenticator, hass.config.time_zone, hass.config.language
        )

    async def _async_update_data(self):
        """Update data from Nintendo's API."""
        try:
            with contextlib.suppress(InvalidSessionTokenException):
                async with asyncio.timeout(self.update_interval.total_seconds() - 5):
                    return await self.api.update()
        except InvalidOAuthConfigurationException as err:
            raise ConfigEntryAuthFailed(err) from err
        except TimeoutError as err:
            raise UpdateFailed(err) from err
        return False
