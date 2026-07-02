"""Data update coordinator for KEBA P40."""

from dataclasses import dataclass
import logging

from keba_kecontact_p40 import (
    KebaP40AuthError,
    KebaP40Client,
    KebaP40Error,
    LoadManagement,
    Wallbox,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type KebaP40ConfigEntry = ConfigEntry[KebaP40DataUpdateCoordinator]


@dataclass
class KebaP40Data:
    """Polled data for one wallbox."""

    wallbox: Wallbox
    load_management: LoadManagement


class KebaP40DataUpdateCoordinator(DataUpdateCoordinator[KebaP40Data]):
    """Coordinator that polls one KEBA P40 wallbox."""

    config_entry: KebaP40ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KebaP40ConfigEntry,
        client: KebaP40Client,
        serial: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.serial = serial

    async def _async_update_data(self) -> KebaP40Data:
        """Fetch the latest wallbox state and load-management bounds."""
        try:
            wallbox = await self.client.get_wallbox(self.serial)
            load_management = await self.client.get_load_management()
        except KebaP40AuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except KebaP40Error as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
        return KebaP40Data(wallbox=wallbox, load_management=load_management)
