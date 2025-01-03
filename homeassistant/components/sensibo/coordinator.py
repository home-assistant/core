"""DataUpdateCoordinator for the Sensibo integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

if TYPE_CHECKING:
    from . import SensiboConfigEntry

REQUEST_REFRESH_DELAY = 0.35


class SensiboDataUpdateCoordinator(DataUpdateCoordinator[SensiboData]):
    """A Sensibo Data Update Coordinator."""

    config_entry: SensiboConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SensiboConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.client = SensiboClient(
            self.config_entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
            timeout=TIMEOUT,
        )

    async def _async_update_data(self) -> SensiboData:
        """Fetch data from Sensibo."""
        try:
            data = await self.client.async_get_devices_data()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from error
        except SensiboError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error

        if not data.raw:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_data")
        return data
