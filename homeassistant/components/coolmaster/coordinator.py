"""DataUpdateCoordinator for coolmaster integration."""

from __future__ import annotations

import asyncio
import logging

from pycoolmasternet_async import CoolMasterNet
from pycoolmasternet_async.coolmasternet import CoolMasterNetUnit

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BACKOFF_BASE_DELAY, DOMAIN, MAX_RETRIES

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
        status: dict[str, CoolMasterNetUnit] = {}
        while retries_left > 0 and not status:
            retries_left -= 1
            try:
                status = await self._coolmaster.status()
            except OSError as error:
                if retries_left == 0:
                    raise UpdateFailed(
                        f"Error communicating with Coolmaster (aborting after {MAX_RETRIES} retries): {error}"
                    ) from error
                _LOGGER.debug(
                    "Error communicating with coolmaster (%d retries left): %s",
                    retries_left,
                    str(error),
                )
            else:
                if status:
                    return status

                _LOGGER.debug(
                    "Error communicating with coolmaster: empty status received (%d retries left)",
                    retries_left,
                )

            backoff = BACKOFF_BASE_DELAY ** (MAX_RETRIES - retries_left)
            await asyncio.sleep(backoff)

        raise UpdateFailed(
            f"Error communicating with Coolmaster (aborting after {MAX_RETRIES} retries): empty status received"
        )
