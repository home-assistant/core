"""Coordinator for the Vitesy integration."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import override

from aiovitesy.api import VitesyApi, VitesyDevice
from aiovitesy.exceptions import CannotAuthenticate, VitesyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type VitesyConfigEntry = ConfigEntry[VitesyDataUpdateCoordinator]

UPDATE_INTERVAL = timedelta(minutes=5)


@contextmanager
def _translate_errors() -> Iterator[None]:
    """Convert aiovitesy errors into coordinator setup/update failures."""
    try:
        yield
    except CannotAuthenticate as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except VitesyError as err:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err


class VitesyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, VitesyDevice]]):
    """Fetch state for every device of a Vitesy Hub account."""

    config_entry: VitesyConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: VitesyConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = VitesyApi(
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
            async_get_clientsession(hass),
        )

    @override
    async def _async_setup(self) -> None:
        """Authenticate against Vitesy Hub before the first refresh."""
        with _translate_errors():
            await self.api.login()

    @override
    async def _async_update_data(self) -> dict[str, VitesyDevice]:
        """Fetch the latest state for every device in the account."""
        with _translate_errors():
            return await self.api.get_all_devices()
