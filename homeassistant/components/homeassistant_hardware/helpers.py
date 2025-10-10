"""Home Assistant Hardware integration helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import logging
from typing import TYPE_CHECKING, Protocol, TypedDict

from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.components.usb import (
    USBDevice,
    async_get_usb_matchers_for_device,
    usb_device_from_path,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback
from homeassistant.exceptions import HomeAssistantError

from . import DATA_COMPONENT
from .const import HARDWARE_INTEGRATION_DOMAINS, YELLOW_DOMAIN

if TYPE_CHECKING:
    from .util import FirmwareInfo


_LOGGER = logging.getLogger(__name__)


class HardwareFirmwareDiscoveryInfo(TypedDict):
    """Data for triggering hardware integration discovery via firmware notification."""

    usb_device: USBDevice | None
    firmware_info: FirmwareInfo


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


async def async_get_hardware_domain_for_usb_device(
    hass: HomeAssistant, usb_device: USBDevice
) -> str | None:
    """Identify which hardware domain should handle a USB device."""
    matched = async_get_usb_matchers_for_device(hass, usb_device)
    hw_domains = {match["domain"] for match in matched} & HARDWARE_INTEGRATION_DOMAINS

    if not hw_domains:
        _LOGGER.debug("No hardware integration matches USB device %r", usb_device)
        return None

    # We can never have two hardware integrations overlap in discovery
    assert len(hw_domains) == 1

    return list(hw_domains)[0]


class HardwareInfoDispatcher:
    """Central dispatcher for hardware/firmware information."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dispatcher."""
        self.hass = hass
        self._providers: dict[str, HardwareFirmwareInfoModule] = {}
        self._notification_callbacks: defaultdict[
            str, set[Callable[[FirmwareInfo], None]]
        ] = defaultdict(set)
        self._active_firmware_updates: dict[str, str] = {}

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

        for callback in list(self._notification_callbacks[firmware_info.device]):
            try:
                callback(firmware_info)
            except Exception:
                _LOGGER.exception(
                    "Error while notifying firmware info listener %s", callback
                )

        await self._async_trigger_hardware_discovery(firmware_info)

    async def _async_trigger_hardware_discovery(
        self, firmware_info: FirmwareInfo
    ) -> None:
        """Trigger hardware integration config flows from firmware info.

        Identifies which hardware integration should handle the device based on
        USB matchers, then triggers an import flow for only that integration.
        """

        usb_device = await self.hass.async_add_executor_job(
            usb_device_from_path, firmware_info.device
        )

        hardware_domain: str | None

        if usb_device is None:
            # Yellow does not have a USB device and needs to be handled explicitly
            try:
                yellow_hardware.async_info(self.hass)
            except HomeAssistantError:
                _LOGGER.debug("No USB device found for device %s", firmware_info.device)
                return
            else:
                hardware_domain = YELLOW_DOMAIN
        else:
            # Other devices need to be checked against USB matchers
            hardware_domain = await async_get_hardware_domain_for_usb_device(
                self.hass, usb_device
            )

        if hardware_domain is None:
            _LOGGER.debug("No hardware integration found for device %s", usb_device)
            return

        _LOGGER.debug(
            "Triggering %s import flow for device %s",
            hardware_domain,
            firmware_info.device,
        )

        await self.hass.config_entries.flow.async_init(
            hardware_domain,
            context={"source": SOURCE_IMPORT},
            data=HardwareFirmwareDiscoveryInfo(
                usb_device=usb_device,
                firmware_info=firmware_info,
            ),
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

    def register_firmware_update_in_progress(
        self, device: str, source_domain: str
    ) -> None:
        """Register that a firmware update is in progress for a device."""
        if device in self._active_firmware_updates:
            current_domain = self._active_firmware_updates[device]
            raise ValueError(
                f"Firmware update already in progress for {device} by {current_domain}"
            )
        self._active_firmware_updates[device] = source_domain

    def unregister_firmware_update_in_progress(
        self, device: str, source_domain: str
    ) -> None:
        """Unregister a firmware update for a device."""
        if device not in self._active_firmware_updates:
            raise ValueError(f"No firmware update in progress for {device}")

        if self._active_firmware_updates[device] != source_domain:
            current_domain = self._active_firmware_updates[device]
            raise ValueError(
                f"Firmware update for {device} is owned by {current_domain}, not {source_domain}"
            )

        del self._active_firmware_updates[device]

    def is_firmware_update_in_progress(self, device: str) -> bool:
        """Check if a firmware update is in progress for a device."""
        return device in self._active_firmware_updates


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


@hass_callback
def async_register_firmware_update_in_progress(
    hass: HomeAssistant, device: str, source_domain: str
) -> None:
    """Register that a firmware update is in progress for a device."""
    return hass.data[DATA_COMPONENT].register_firmware_update_in_progress(
        device, source_domain
    )


@hass_callback
def async_unregister_firmware_update_in_progress(
    hass: HomeAssistant, device: str, source_domain: str
) -> None:
    """Unregister a firmware update for a device."""
    return hass.data[DATA_COMPONENT].unregister_firmware_update_in_progress(
        device, source_domain
    )


@hass_callback
def async_is_firmware_update_in_progress(hass: HomeAssistant, device: str) -> bool:
    """Check if a firmware update is in progress for a device."""
    return hass.data[DATA_COMPONENT].is_firmware_update_in_progress(device)


@asynccontextmanager
async def async_firmware_update_context(
    hass: HomeAssistant, device: str, source_domain: str
) -> AsyncIterator[None]:
    """Register a device as having its firmware being actively updated."""
    async_register_firmware_update_in_progress(hass, device, source_domain)

    try:
        yield
    finally:
        async_unregister_firmware_update_in_progress(hass, device, source_domain)
