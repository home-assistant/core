"""DataUpdateCoordinator for Verizon FiOS Quantum Gateway."""

from datetime import timedelta
import logging
from typing import override

from quantum_gateway import QuantumGatewayScanner

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type QuantumGatewayConfigEntry = ConfigEntry[QuantumGatewayDataUpdateCoordinator]


class QuantumGatewayDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Class to manage fetching data from the Quantum Gateway."""

    config_entry: QuantumGatewayConfigEntry
    scanner: QuantumGatewayScanner | None = None

    def __init__(
        self, hass: HomeAssistant, config_entry: QuantumGatewayConfigEntry
    ) -> None:
        """Initialize the coordinator using config entry."""

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {config_entry.data[CONF_HOST]}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _get_scanner(self) -> QuantumGatewayScanner:
        scanner = await self.hass.async_add_executor_job(
            QuantumGatewayScanner,
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_PASSWORD],
            self.config_entry.data[CONF_SSL],
        )

        if not scanner.success_init:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            )

        return scanner

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from the Quantum Gateway."""
        try:
            if self.scanner is None:
                self.scanner = await self._get_scanner()

            macs = await self.hass.async_add_executor_job(self.scanner.scan_devices)
            return {mac: self.scanner.get_device_name(mac) for mac in macs}

        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            raise UpdateFailed(
                f"Failed to fetch data from Quantum Gateway {self.config_entry.data[CONF_HOST]}"
            ) from err
