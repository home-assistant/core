"""Retrieve local measurements and maintain the controller lease."""

from datetime import timedelta
import logging
import time
from typing import override

from terrestream_local import Client
from terrestream_local.errors import AuthenticationError, ClientError
from terrestream_local.models import Snapshot

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
type TerrestreamConfigEntry = ConfigEntry[TerrestreamCoordinator]


class TerrestreamCoordinator(DataUpdateCoordinator[Snapshot]):
    """Poll the sensor without extending acquisition freshness."""

    def __init__(
        self, hass: HomeAssistant, entry: TerrestreamConfigEntry, client: Client
    ) -> None:
        """Initialize polling for the authenticated sensor."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=5),
        )
        self.client = client
        self._next_clock = 0.0

    @override
    async def _async_update_data(self) -> Snapshot:
        try:
            data = await self.client.refresh()
            if time.monotonic() >= self._next_clock:
                await self.client.command(
                    "time", epoch=int(time.time()), uncertainty_ms=1000
                )
                self._next_clock = time.monotonic() + 60
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="pairing_revoked"
            ) from err
        except ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        return data

    async def async_release(self) -> None:
        """Release the lease after stopping polling; offline leases expire."""
        await self.async_shutdown()
        try:
            await self.client.command("release")
        except ClientError:
            _LOGGER.debug("Sensor unavailable while releasing controller lease")
