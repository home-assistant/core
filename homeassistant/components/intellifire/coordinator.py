"""The IntelliFire integration."""

from __future__ import annotations

from datetime import timedelta

from intellifire4py import UnifiedFireplace
from intellifire4py.const import IntelliFireApiMode
from intellifire4py.control import IntelliFireController
from intellifire4py.model import IntelliFirePollData
from intellifire4py.read import IntelliFireDataProvider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER

type IntellifireConfigEntry = ConfigEntry[IntellifireDataUpdateCoordinator]


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator[IntelliFirePollData]):
    """Class to manage the polling of the fireplace API."""

    config_entry: IntellifireConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IntellifireConfigEntry,
        fireplace: UnifiedFireplace,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )

        self.fireplace = fireplace

    @property
    def read_api(self) -> IntelliFireDataProvider:
        """Return the Status API pointer."""
        return self.fireplace.read_api

    @property
    def control_api(self) -> IntelliFireController:
        """Return the control API."""
        return self.fireplace.control_api

    def get_read_mode(self) -> IntelliFireApiMode:
        """Return the current read mode."""
        return self.fireplace.read_mode

    async def set_read_mode(self, mode: IntelliFireApiMode) -> None:
        """Set the read mode between cloud/local."""
        await self.fireplace.set_read_mode(mode)

    def get_control_mode(self) -> IntelliFireApiMode:
        """Return the current control mode."""
        return self.fireplace.control_mode

    async def set_control_mode(self, mode: IntelliFireApiMode) -> None:
        """Set the control mode between cloud/local."""
        await self.fireplace.set_control_mode(mode)

    async def _async_update_data(self) -> IntelliFirePollData:
        await self.fireplace.perform_poll()
        return self.fireplace.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            manufacturer="Hearth and Home",
            model="IFT-WFM",
            name="IntelliFire",
            identifiers={("IntelliFire", str(self.fireplace.serial))},
            configuration_url=f"http://{self.fireplace.ip_address}/poll",
        )
