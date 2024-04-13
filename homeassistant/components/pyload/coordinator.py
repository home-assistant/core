"""Update coordinator for pyLoad Integration."""

from datetime import timedelta
import logging

from pyloadapi.api import PyLoadAPI
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError

from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class PyLoadCoordinator(DataUpdateCoordinator):
    """pyLoad coordinator."""

    def __init__(self, hass: HomeAssistant, pyload: PyLoadAPI) -> None:
        """Initialize pyLoad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pyload = pyload

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return await self.pyload.get_status()
        except InvalidAuth:
            _LOGGER.info("Authentication failed, trying to reauthenticate")
            try:
                await self.pyload.login()
            except InvalidAuth as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_exception",
                    translation_placeholders={CONF_USERNAME: self.pyload.username},
                ) from e
        except CannotConnect as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from pyLoad API"
            ) from e
        except ParserError as e:
            raise UpdateFailed("Unable to parse data from pyLoad API") from e
