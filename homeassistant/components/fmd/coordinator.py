"""Data update coordinator for the FMD integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from fmd_api import AuthenticationError, FmdApiException, FmdClient
from fmd_api.models import Location

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_POLLING_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import FmdConfigEntry

_LOGGER = logging.getLogger(__name__)


class FmdCoordinator(DataUpdateCoordinator[Location]):
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
    async def _async_update_data(self) -> Location:
        """Fetch the latest validated location fix from the FMD server."""
        try:
            location = await self.api.get_latest_location(
                filter_inaccurate=self.filter_inaccurate
            )
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="update_auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except FmdApiException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if location is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_location_data",
            )
        return location
