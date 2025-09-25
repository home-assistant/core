"""DataUpdateCoordinator for Dynamic DNS."""

from datetime import timedelta
import logging

from dynamicdns import Provider, Updater

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PROVIDER, DOMAIN

type DynamicDnsConfigEntry = ConfigEntry[DynamicDnsUpdateCoordinator]


_LOGGER = logging.getLogger(__name__)


class DynamicDnsUpdateCoordinator(DataUpdateCoordinator[None]):
    """Dynamic DNS Update Coordinator."""

    client: Updater
    config_entry: DynamicDnsConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: DynamicDnsConfigEntry
    ) -> None:
        """Initialize the update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=120),
        )

    async def _async_setup(self) -> None:
        """Set up coordinator."""

        session = async_get_clientsession(self.hass)
        self.client = Updater(
            provider=Provider(self.config_entry.data[CONF_PROVIDER]),
            data={**self.config_entry.data},
            session=session,
        )

    async def _async_update_data(self) -> None:
        """Update DNS record."""

        if not await self.client.update():
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )
