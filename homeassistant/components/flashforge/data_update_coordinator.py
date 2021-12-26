"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta
import logging

from ffpp.Printer import Printer

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlashForgeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FlashForgeprinter data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        printer: Printer,
        config_entry: ConfigEntry,
        interval: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DEFAULT_NAME}-{config_entry.entry_id}",
            update_interval=timedelta(seconds=interval),
            update_method=self.async_update_data,
        )
        self.config_entry = config_entry
        self.printer = printer
        self._printer_offline = False
        self.data = {
            "status": None,
        }

    async def async_update_data(self):
        """Update data via API."""
        try:
            await self.printer.update()
        except TimeoutError as e:
            raise UpdateFailed(e) from e
        except ConnectionError as e:
            raise UpdateFailed(e) from e

        return {
            "status": self.printer.status,
        }

    async def async_config_entry_first_refresh(self):
        """Connect to printer and update with machine info."""
        try:
            await self.printer.updateMachineInfo(disconnect=False)
        except TimeoutError as e:
            raise UpdateFailed(e) from e
        except ConnectionError as e:
            raise UpdateFailed(e) from e

        return await super().async_config_entry_first_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        unique_id = self.config_entry.unique_id or ""
        model = self.printer.machine_type
        name = self.printer.machine_name
        firmware = self.printer.firmware

        return DeviceInfo(
            configuration_url=None,
            identifiers={(DOMAIN, unique_id)},
            manufacturer="FlashForge",
            model=model,
            name=name,
            sw_version=firmware,
        )
