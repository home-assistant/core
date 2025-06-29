"""Coordinator for the Quantum Gateway integration."""

from typing import override

from quantum_gateway import QuantumGatewayScanner

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


def get_scanner(host: str, password: str, use_https: bool) -> QuantumGatewayScanner:
    """Return a Quantum Gateway scanner."""
    return QuantumGatewayScanner(host, password, use_https)


class QuantumGatewayCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Class to manage fetching data from the Quantum Gateway router."""

    scanner: QuantumGatewayScanner | None

    def __init__(self, hass: HomeAssistant, options: ConfigType) -> None:
        """Initialize the data coordinator."""
        update_interval = options.get(CONF_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name="Quantum Gateway device scanner",
            update_interval=update_interval,
            always_update=False,
        )
        self.options = options

    @override
    async def _async_setup(self):
        """Set up the Quantum Gateway device scanner."""
        self.scanner = await self.hass.async_add_executor_job(
            get_scanner,
            self.options[CONF_HOST],
            self.options[CONF_PASSWORD],
            self.options[CONF_SSL],
        )

    @override
    async def _async_update_data(self):
        """Fetch the latest data from the Quantum Gateway."""
        if self.scanner is None:
            raise UpdateFailed("Scanner not initialized.")
        try:
            macs = await self.hass.async_add_executor_job(self.scanner.scan_devices)
            return {mac: self.scanner.get_device_name(mac) for mac in macs}
        except Exception as err:
            raise UpdateFailed(f"Error scanning for devices: {err}") from err
