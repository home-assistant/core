"""Retrieve local measurements and maintain the controller lease."""

from asyncio import timeout
from datetime import timedelta
import logging
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
# Finish before config entry unload stops waiting for pending tasks.
_LEASE_RELEASE_TIMEOUT = 5

type TerrestreamConfigEntry = ConfigEntry[TerrestreamCoordinator]


class TerrestreamCoordinator(DataUpdateCoordinator[Snapshot]):
    """Poll the sensor for its latest measurements."""

    def __init__(
        self, hass: HomeAssistant, entry: TerrestreamConfigEntry, client: Client
    ) -> None:
        """Initialize polling for the authenticated sensor."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> Snapshot:
        try:
            snapshot = await self.client.refresh()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="pairing_revoked"
            ) from err
        except ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        return {
            **snapshot,
            "measurements": {
                key: {
                    **measurement,
                    "available": self.client.measurement_available(key),
                }
                for key, measurement in snapshot["measurements"].items()
            },
        }

    async def async_release(self) -> None:
        """Release the lease after stopping polling; offline leases expire."""
        await self.async_shutdown()
        try:
            async with (
                timeout(_LEASE_RELEASE_TIMEOUT),
                self._debounced_refresh.async_lock(),
            ):
                await self.client.command("release")
        except TimeoutError:
            _LOGGER.debug(
                "Controller lease release timed out; letting the lease expire"
            )
        except ClientError:
            _LOGGER.debug("Sensor unavailable while releasing controller lease")
