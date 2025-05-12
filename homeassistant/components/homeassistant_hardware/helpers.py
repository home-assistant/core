"""Home Assistant Hardware integration helpers."""

from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
import logging
from typing import Protocol

from universal_silabs_flasher.firmware import parse_firmware_image
from universal_silabs_flasher.flasher import Flasher

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback
from homeassistant.exceptions import HomeAssistantError

from . import DATA_COMPONENT
from .util import (
    ApplicationType,
    FirmwareInfo,
    guess_firmware_info,
    probe_silabs_firmware_info,
)

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
        self._notification_callbacks: defaultdict[
            str, set[Callable[[FirmwareInfo], None]]
        ] = defaultdict(set)

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

    def register_firmware_info_callback(
        self, device: str, callback: Callable[[FirmwareInfo], None]
    ) -> CALLBACK_TYPE:
        """Register a firmware info notification callback."""
        self._notification_callbacks[device].add(callback)

        @hass_callback
        def async_remove_callback() -> None:
            self._notification_callbacks[device].discard(callback)

        return async_remove_callback

    async def notify_firmware_info(
        self, domain: str, firmware_info: FirmwareInfo
    ) -> None:
        """Notify the dispatcher of new firmware information."""
        _LOGGER.debug(
            "Received firmware info notification from %r: %s", domain, firmware_info
        )

        for callback in self._notification_callbacks.get(firmware_info.device, []):
            try:
                callback(firmware_info)
            except Exception:
                _LOGGER.exception(
                    "Error while notifying firmware info listener %s", callback
                )

    async def iter_firmware_info(self) -> AsyncIterator[FirmwareInfo]:
        """Iterate over all firmware information for all hardware."""
        for domain, fw_info_module in self._providers.items():
            for config_entry in self.hass.config_entries.async_entries(domain):
                try:
                    if hasattr(fw_info_module, "get_firmware_info"):
                        fw_info = fw_info_module.get_firmware_info(
                            self.hass, config_entry
                        )
                    else:
                        fw_info = await fw_info_module.async_get_firmware_info(
                            self.hass, config_entry
                        )
                except Exception:
                    _LOGGER.exception(
                        "Error while getting firmware info from %r", fw_info_module
                    )
                    continue

                if fw_info is not None:
                    yield fw_info


@hass_callback
def async_register_firmware_info_provider(
    hass: HomeAssistant, domain: str, platform: HardwareFirmwareInfoModule
) -> None:
    """Register a firmware info provider."""
    return hass.data[DATA_COMPONENT].register_firmware_info_provider(domain, platform)


@hass_callback
def async_register_firmware_info_callback(
    hass: HomeAssistant, device: str, callback: Callable[[FirmwareInfo], None]
) -> CALLBACK_TYPE:
    """Register a firmware info provider."""
    return hass.data[DATA_COMPONENT].register_firmware_info_callback(device, callback)


@hass_callback
def async_notify_firmware_info(
    hass: HomeAssistant, domain: str, firmware_info: FirmwareInfo
) -> Awaitable[None]:
    """Notify the dispatcher of new firmware information."""
    return hass.data[DATA_COMPONENT].notify_firmware_info(domain, firmware_info)


async def async_flash_silabs_firmware(
    hass: HomeAssistant,
    device: str,
    fw_data: bytes,
    expected_installed_firmware_type: ApplicationType,
    bootloader_reset_type: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> FirmwareInfo:
    """Flash firmware to the SiLabs device."""
    firmware_info = await guess_firmware_info(hass, device)
    _LOGGER.debug("Identified firmware info: %s", firmware_info)

    fw_image = await hass.async_add_executor_job(parse_firmware_image, fw_data)

    flasher = Flasher(
        device=device,
        probe_methods=(
            ApplicationType.GECKO_BOOTLOADER.as_flasher_application_type(),
            ApplicationType.EZSP.as_flasher_application_type(),
            ApplicationType.SPINEL.as_flasher_application_type(),
            ApplicationType.CPC.as_flasher_application_type(),
        ),
        bootloader_reset=bootloader_reset_type,
    )

    async with AsyncExitStack() as stack:
        for owner in firmware_info.owners:
            await stack.enter_async_context(owner.temporarily_stop(hass))

        try:
            # Enter the bootloader with indeterminate progress
            await flasher.enter_bootloader()

            # Flash the firmware, with progress
            await flasher.flash_firmware(fw_image, progress_callback=progress_callback)
        except Exception as err:
            raise HomeAssistantError("Failed to flash firmware") from err

        probed_firmware_info = await probe_silabs_firmware_info(
            device,
            probe_methods=(expected_installed_firmware_type,),
        )

    if probed_firmware_info is None:
        raise HomeAssistantError("Failed to probe the firmware after flashing")

    return probed_firmware_info
