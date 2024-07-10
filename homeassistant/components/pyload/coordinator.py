"""Update coordinator for pyLoad Integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyloadapi import CannotConnect, InvalidAuth, ParserError, PyLoadAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=20)


@dataclass(kw_only=True)
class PyLoadData:
    """Data from pyLoad."""

    pause: bool
    active: int
    queue: int
    total: int
    speed: float
    download: bool
    reconnect: bool
    captcha: bool | None = None
    free_space: int


class PyLoadCoordinator(DataUpdateCoordinator[PyLoadData]):
    """pyLoad coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, pyload: PyLoadAPI) -> None:
        """Initialize pyLoad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pyload = pyload
        self.version: str | None = None

    async def _async_update_data(self) -> PyLoadData:
        """Fetch data from API endpoint."""
        try:
            if not self.version:
                self.version = await self.pyload.version()
            return PyLoadData(
                **await self.pyload.get_status(),
                free_space=await self.pyload.free_space(),
            )

        except InvalidAuth as e:
            try:
                await self.pyload.login()
            except InvalidAuth as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={CONF_USERNAME: self.pyload.username},
                ) from exc

            raise UpdateFailed(
                "Unable to retrieve data due to cookie expiration"
            ) from e
        except CannotConnect as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from pyLoad API"
            ) from e
        except ParserError as e:
            raise UpdateFailed("Unable to parse data from pyLoad API") from e
