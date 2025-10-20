"""Nintendo parental controls data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pynintendoparental import Authenticator, NintendoParental
from pynintendoparental.exceptions import (
    InvalidOAuthConfigurationException,
    NoDevicesFoundException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .repairs import raise_no_devices_found

type NintendoParentalControlsConfigEntry = ConfigEntry[NintendoUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=60)


class NintendoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Nintendo data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        authenticator: Authenticator,
        config_entry: NintendoParentalControlsConfigEntry,
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

    async def _async_update_data(self) -> None:
        """Update data from Nintendo's API."""
        try:
            return await self.api.update()
        except InvalidOAuthConfigurationException as err:
            raise ConfigEntryError(
                err, translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except NoDevicesFoundException as err:
            if TYPE_CHECKING:
                assert self.config_entry is not None
            raise_no_devices_found(self.hass, self.config_entry)
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="no_devices_found",
            ) from err
