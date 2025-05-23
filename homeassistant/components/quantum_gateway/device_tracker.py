"""Support for Verizon FiOS Quantum Gateways."""

from __future__ import annotations

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DATA_COODINATOR, DOMAIN, LOGGER, PLATFORM_SCHEMA  # noqa: F401
from .coordinator import QuantumGatewayCoordinator


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> QuantumGatewayDeviceScanner | None:
    """Validate the configuration and return a Quantum Gateway scanner."""
    coordinator = hass.data[DOMAIN][config[DEVICE_TRACKER_DOMAIN][CONF_HOST]][
        DATA_COODINATOR
    ]
    if coordinator is None:
        return None

    return QuantumGatewayDeviceScanner(hass, coordinator)


class QuantumGatewayDeviceScanner(DeviceScanner):
    """Class which queries a Quantum Gateway."""

    def __init__(
        self, hass: HomeAssistant, coordinator: QuantumGatewayCoordinator
    ) -> None:
        """Initialize the scanner."""

        LOGGER.debug("Initializing")

        self.coordinator = coordinator

    async def async_scan_devices(self) -> list[str]:
        """Scan for new devices and return a list of found MACs."""
        await self.coordinator.async_refresh()
        return list(self.coordinator.data)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        return self.coordinator.data.get(device)
