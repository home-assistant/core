"""Coordinator for LinknLink devices."""

from typing import override

from aiolinknlink import UltraClient, UltraDevice, UltraError, UltraSession, UltraState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER

type LinknLinkConfigEntry = ConfigEntry[LinknLinkCoordinator]


class LinknLinkCoordinator(DataUpdateCoordinator[UltraState]):
    """Coordinate updates from one eMotion Ultra device."""

    config_entry: LinknLinkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LinknLinkConfigEntry,
        client: UltraClient,
        device: UltraDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"LinknLink {device.id}",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.client = client
        self.device = device
        self.session: UltraSession | None = None

    @override
    async def _async_setup(self) -> None:
        """Authenticate with the device before the first refresh."""
        try:
            self.session = await self.client.connect(self.device)
        except UltraError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

    @override
    async def _async_update_data(self) -> UltraState:
        """Fetch the latest state from the device."""
        assert self.session is not None
        try:
            return await self.client.refresh(self.session)
        except UltraError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
