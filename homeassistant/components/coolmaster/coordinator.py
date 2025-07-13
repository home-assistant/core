"""DataUpdateCoordinator for coolmaster integration."""

from __future__ import annotations

import logging

from pycoolmasternet_async import CoolMasterNet
from pycoolmasternet_async.coolmasternet import CoolMasterNetUnit

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_RETRIES

_LOGGER = logging.getLogger(__name__)


type CoolmasterConfigEntry = ConfigEntry[CoolmasterDataUpdateCoordinator]


class CoolmasterDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, CoolMasterNetUnit]]
):
    """Class to manage fetching Coolmaster data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CoolmasterConfigEntry,
        coolmaster: CoolMasterNet,
        info: dict[str, str],
    ) -> None:
        """Initialize global Coolmaster data updater."""
        self._coolmaster = coolmaster
        self.info = info

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, CoolMasterNetUnit]:
        """Fetch data from Coolmaster."""
        retries_left = MAX_RETRIES
        while retries_left > 0:
            try:
                return await self._coolmaster.status()
            except OSError as error:
                retries_left -= 1
                if retries_left == 0:
                    _LOGGER.error(
                        "Error communicating with Coolmaster (aborting after %d retries): %s",
                        MAX_RETRIES,
                        str(error),
                    )
                    raise UpdateFailed from error
                _LOGGER.debug(
                    "Error communicating with coolmaster (%d retries left): %s",
                    retries_left,
                    str(error),
                )

        # This code will never run but without it mypy will complain about missing return
        return await self._coolmaster.status()
