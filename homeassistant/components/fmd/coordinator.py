"""Data update coordinator for the FMD integration."""

from datetime import timedelta
import json
import logging
from typing import TYPE_CHECKING, Any, override

from fmd_api import AuthenticationError, FmdApiException, FmdClient

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_POLLING_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import FmdConfigEntry

_LOGGER = logging.getLogger(__name__)

_ACCURATE_PROVIDERS = {"fused", "gps", "network"}
_INACCURATE_PROVIDERS = {"beacondb", ""}


def is_location_accurate(location: dict[str, Any]) -> bool:
    """Return True if the location's provider is considered accurate.

    Fused, GPS and network fixes are trusted; BeaconDB and unknown
    providers are not.
    """
    provider = str(location.get("provider") or "").lower()
    return provider in _ACCURATE_PROVIDERS


class FmdCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage fetching FMD location data for a single account."""

    config_entry: FmdConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: FmdClient, entry: FmdConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.filter_inaccurate = not bool(entry.data.get("allow_inaccurate_locations"))
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_ID]}",
            update_interval=timedelta(minutes=DEFAULT_POLLING_INTERVAL),
            config_entry=entry,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest location data from the FMD server."""
        try:
            blobs = await self.api.get_locations(5 if self.filter_inaccurate else 1)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="update_auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except FmdApiException as err:
            if self.data:
                # Transient API error: keep serving the last known location.
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        for blob in blobs:
            if not blob:
                continue
            decrypted = await self.hass.async_add_executor_job(
                self.api.decrypt_data_blob, blob
            )
            location: dict[str, Any] = json.loads(decrypted)
            if self.filter_inaccurate and not is_location_accurate(location):
                _LOGGER.debug(
                    "Skipping inaccurate location (provider=%s)",
                    location.get("provider"),
                )
                continue
            return location

        if self.data:
            # No acceptable new fix; keep serving the previous location.
            return self.data
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="no_location_data",
        )
