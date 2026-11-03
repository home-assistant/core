"""Data update coordinator for E3/DC devices."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from e3dc_ess_modbus import E3dcPowerStation, NotAnE3dcError
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# The components the entities read
POLLED_COMPONENTS = ("power",)
# The components that tell which optional hardware is installed, read once
HARDWARE_COMPONENTS = ("wallboxes", "power_meters")

type E3dcConfigEntry = ConfigEntry[E3dcDataUpdateCoordinator]


class E3dcDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Poll the power flows of the power station."""

    config_entry: E3dcConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: E3dcConfigEntry,
        device: E3dcPowerStation,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        identity = self.device.identity
        serial = self.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        return dr.DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=identity.manufacturer or DEFAULT_NAME,
            model=identity.model or None,
            serial_number=identity.serial_number or None,
            sw_version=identity.firmware_release or None,
        )

    @override
    async def _async_setup(self) -> None:
        await self._async_poll(HARDWARE_COMPONENTS)

    @override
    async def _async_update_data(self) -> None:
        await self._async_poll(POLLED_COMPONENTS)

    async def _async_poll(self, components: tuple[str, ...]) -> None:
        """Read the components from the power station, or raise."""
        try:
            report = await self.device.async_poll(components)
        except NotAnE3dcError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="not_e3dc",
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if report.failed:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from ExceptionGroup(
                "components failed to refresh", list(report.failed.values())
            )
