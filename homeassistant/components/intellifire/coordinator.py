"""The IntelliFire integration."""

from __future__ import annotations

from datetime import timedelta

from intellifire4py import UnifiedFireplace
from intellifire4py.control import IntelliFireController
from intellifire4py.model import IntelliFirePollData
from intellifire4py.read import IntelliFireDataProvider

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator[IntelliFirePollData]):
    """Class to manage the polling of the fireplace API."""

    def __init__(
        self,
        hass: HomeAssistant,
        fireplace: UnifiedFireplace,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
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

    async def _async_update_data(self) -> IntelliFirePollData:
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
