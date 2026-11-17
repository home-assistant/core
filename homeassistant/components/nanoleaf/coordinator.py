"""Define the Nanoleaf data coordinator."""

from datetime import timedelta
import logging
from typing import override

from aionanoleaf2 import AuthError, Nanoleaf, NanoleafError, NoAuthToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type NanoleafConfigEntry = ConfigEntry[NanoleafCoordinator]


class NanoleafCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Nanoleaf data."""

    config_entry: NanoleafConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: NanoleafConfigEntry, nanoleaf: Nanoleaf
    ) -> None:
        """Initialize the Nanoleaf data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Nanoleaf",
            update_interval=timedelta(minutes=1),
        )
        self.nanoleaf = nanoleaf

    @override
    async def _async_update_data(self) -> None:
        try:
            await self.nanoleaf.get_info()
        except (AuthError, NoAuthToken) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_token"
            ) from err
        except NanoleafError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
