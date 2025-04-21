"""Update coordinator for pyLoad Integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyloadapi import CannotConnect, InvalidAuth, ParserError, PyLoadAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
    proxy: bool | None = None
    free_space: int


type PyLoadConfigEntry = ConfigEntry[PyLoadCoordinator]


class PyLoadCoordinator(DataUpdateCoordinator[PyLoadData]):
    """pyLoad coordinator."""

    config_entry: PyLoadConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: PyLoadConfigEntry, pyload: PyLoadAPI
    ) -> None:
        """Initialize pyLoad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pyload = pyload
        self.version: str | None = None

    async def _async_update_data(self) -> PyLoadData:
        """Fetch data from API endpoint."""
        try:
            return PyLoadData(
                **await self.pyload.get_status(),
                free_space=await self.pyload.free_space(),
            )
        except InvalidAuth:
            try:
                await self.pyload.login()
            except InvalidAuth as exc:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="setup_authentication_exception",
                    translation_placeholders={CONF_USERNAME: self.pyload.username},
                ) from exc
            _LOGGER.debug(
                "Unable to retrieve data due to cookie expiration, retrying after 20 seconds"
            )
            return self.data
        except CannotConnect as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e
        except ParserError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="setup_parse_exception",
            ) from e

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            await self.pyload.login()
            self.version = await self.pyload.version()
        except CannotConnect as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_request_exception",
            ) from e
        except ParserError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_parse_exception",
            ) from e
        except InvalidAuth as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="setup_authentication_exception",
                translation_placeholders={
                    CONF_USERNAME: self.config_entry.data[CONF_USERNAME]
                },
            ) from e
