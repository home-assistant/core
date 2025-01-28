"""Home Assistant Hardware integration helpers."""

from collections.abc import AsyncIterator, Awaitable
import logging
from typing import Protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from . import DATA_COMPONENT
from .util import FirmwareInfo

_LOGGER = logging.getLogger(__name__)


class SyncHardwareFirmwareInfoModule(Protocol):
    """Protocol type for Home Assistant Hardware firmware info platform modules."""

    def get_firmware_info(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> FirmwareInfo | None:
        """Return radio firmware information for the config entry, synchronously."""


class AsyncHardwareFirmwareInfoModule(Protocol):
    """Protocol type for Home Assistant Hardware firmware info platform modules."""

    async def async_get_firmware_info(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> FirmwareInfo | None:
        """Return radio firmware information for the config entry, asynchronously."""


type HardwareFirmwareInfoModule = (
    SyncHardwareFirmwareInfoModule | AsyncHardwareFirmwareInfoModule
)


class HardwareInfoDispatcher:
    """Central dispatcher for hardware/firmware information."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dispatcher."""
        self.hass = hass
        self._providers: dict[str, HardwareFirmwareInfoModule] = {}

    def register_firmware_info_provider(
        self, domain: str, platform: HardwareFirmwareInfoModule
    ) -> None:
        """Register a firmware info provider."""
        if domain in self._providers:
            raise ValueError(
                f"Domain {domain} is already registered as a firmware info provider"
            )

        # There is no need to handle "unregistration" because integrations cannot be
        # wholly removed at runtime
        self._providers[domain] = platform
        _LOGGER.debug(
            "Registered firmware info provider from domain %r: %s", domain, platform
        )

    async def notify_firmware_info(
        self, domain: str, firmware_info: FirmwareInfo
    ) -> None:
        """Notify the dispatcher of new firmware information."""
        _LOGGER.debug(
            "Received firmware info notification from %r: %s", domain, firmware_info
        )

    async def iter_firmware_info(self) -> AsyncIterator[FirmwareInfo]:
        """Iterate over all firmware information for all hardware."""
        for domain, fw_info_module in self._providers.items():
            for config_entry in self.hass.config_entries.async_entries(domain):
                if hasattr(fw_info_module, "get_firmware_info"):
                    fw_info = fw_info_module.get_firmware_info(self.hass, config_entry)
                else:
                    fw_info = await fw_info_module.async_get_firmware_info(
                        self.hass, config_entry
                    )

                if fw_info is not None:
                    yield fw_info


@callback
def register_firmware_info_provider(
    hass: HomeAssistant, domain: str, platform: HardwareFirmwareInfoModule
) -> None:
    """Register a firmware info provider."""
    return hass.data[DATA_COMPONENT].register_firmware_info_provider(domain, platform)


@callback
def notify_firmware_info(
    hass: HomeAssistant, domain: str, firmware_info: FirmwareInfo
) -> Awaitable[None]:
    """Notify the dispatcher of new firmware information."""
    return hass.data[DATA_COMPONENT].notify_firmware_info(domain, firmware_info)
