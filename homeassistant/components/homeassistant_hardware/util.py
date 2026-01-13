"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
import logging

from universal_silabs_flasher.const import (
    ApplicationType as FlasherApplicationType,
    ResetTarget as FlasherResetTarget,
)
from universal_silabs_flasher.firmware import parse_firmware_image
from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.hassio import AddonError, AddonManager, AddonState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.singleton import singleton

from . import DATA_COMPONENT
from .const import (
    OTBR_ADDON_MANAGER_DATA,
    OTBR_ADDON_NAME,
    OTBR_ADDON_SLUG,
    ZIGBEE_FLASHER_ADDON_MANAGER_DATA,
    ZIGBEE_FLASHER_ADDON_NAME,
    ZIGBEE_FLASHER_ADDON_SLUG,
)
from .helpers import async_firmware_update_context
from .silabs_multiprotocol_addon import (
    WaitingAddonManager,
    get_multiprotocol_addon_manager,
)

_LOGGER = logging.getLogger(__name__)


class ApplicationType(StrEnum):
    """Application type running on a device."""

    GECKO_BOOTLOADER = "bootloader"
    EZSP = "ezsp"
    SPINEL = "spinel"
    CPC = "cpc"
    ROUTER = "router"

    @classmethod
    def from_flasher_application_type(
        cls, app_type: FlasherApplicationType
    ) -> ApplicationType:
        """Convert a USF application type enum."""
        return cls(app_type.value)

    def as_flasher_application_type(self) -> FlasherApplicationType:
        """Convert the application type enum into one compatible with USF."""
        return FlasherApplicationType(self.value)


class ResetTarget(StrEnum):
    """Methods to reset a device into bootloader mode."""

    RTS_DTR = "rts_dtr"
    BAUDRATE = "baudrate"
    YELLOW = "yellow"

    def as_flasher_reset_target(self) -> FlasherResetTarget:
        """Convert the reset target enum into one compatible with USF."""
        return FlasherResetTarget(self.value)


@singleton(OTBR_ADDON_MANAGER_DATA)
@callback
def get_otbr_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the OTBR add-on manager."""
    return WaitingAddonManager(
        hass,
        _LOGGER,
        OTBR_ADDON_NAME,
        OTBR_ADDON_SLUG,
    )


@singleton(ZIGBEE_FLASHER_ADDON_MANAGER_DATA)
@callback
def get_zigbee_flasher_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the flasher add-on manager."""
    return WaitingAddonManager(
        hass,
        _LOGGER,
        ZIGBEE_FLASHER_ADDON_NAME,
        ZIGBEE_FLASHER_ADDON_SLUG,
    )


@dataclass(kw_only=True)
class OwningAddon:
    """Owning add-on."""

    slug: str

    def _get_addon_manager(self, hass: HomeAssistant) -> WaitingAddonManager:
        return WaitingAddonManager(
            hass,
            _LOGGER,
            f"Add-on {self.slug}",
            self.slug,
        )

    async def is_running(self, hass: HomeAssistant) -> bool:
        """Check if the add-on is running."""
        addon_manager = self._get_addon_manager(hass)

        try:
            addon_info = await addon_manager.async_get_addon_info()
        except AddonError:
            return False
        else:
            return addon_info.state == AddonState.RUNNING

    @asynccontextmanager
    async def temporarily_stop(self, hass: HomeAssistant) -> AsyncIterator[None]:
        """Temporarily stop the add-on, restarting it after completion."""
        addon_manager = self._get_addon_manager(hass)

        try:
            addon_info = await addon_manager.async_get_addon_info()
        except AddonError:
            yield
            return

        if addon_info.state != AddonState.RUNNING:
            yield
            return

        try:
            await addon_manager.async_stop_addon()
            await addon_manager.async_wait_until_addon_state(AddonState.NOT_RUNNING)
            yield
        finally:
            await addon_manager.async_start_addon_waiting()


@dataclass(kw_only=True)
class OwningIntegration:
    """Owning integration."""

    config_entry_id: str

    async def is_running(self, hass: HomeAssistant) -> bool:
        """Check if the integration is running."""
        if (entry := hass.config_entries.async_get_entry(self.config_entry_id)) is None:
            return False

        return entry.state in (
            ConfigEntryState.LOADED,
            ConfigEntryState.SETUP_RETRY,
            ConfigEntryState.SETUP_IN_PROGRESS,
        )

    @asynccontextmanager
    async def temporarily_stop(self, hass: HomeAssistant) -> AsyncIterator[None]:
        """Temporarily stop the integration, restarting it after completion."""
        if (entry := hass.config_entries.async_get_entry(self.config_entry_id)) is None:
            yield
            return

        if entry.state != ConfigEntryState.LOADED:
            yield
            return

        try:
            await hass.config_entries.async_unload(entry.entry_id)
            yield
        finally:
            await hass.config_entries.async_setup(entry.entry_id)


@dataclass(kw_only=True)
class FirmwareInfo:
    """Firmware guess."""

    device: str
    firmware_type: ApplicationType
    firmware_version: str | None

    source: str
    owners: list[OwningAddon | OwningIntegration]

    async def is_running(self, hass: HomeAssistant) -> bool:
        """Check if the firmware owner is running."""
        states = await asyncio.gather(*(o.is_running(hass) for o in self.owners))
        if not states:
            return False

        return all(states)


async def get_otbr_addon_firmware_info(
    hass: HomeAssistant, otbr_addon_manager: AddonManager
) -> FirmwareInfo | None:
    """Get firmware info from the OTBR add-on."""
    try:
        otbr_addon_info = await otbr_addon_manager.async_get_addon_info()
    except AddonError:
        return None

    if otbr_addon_info.state == AddonState.NOT_INSTALLED:
        return None

    if (otbr_path := otbr_addon_info.options.get("device")) is None:
        return None

    # Only create a new entry if there are no existing OTBR ones
    return FirmwareInfo(
        device=otbr_path,
        firmware_type=ApplicationType.SPINEL,
        firmware_version=None,
        source="otbr",
        owners=[OwningAddon(slug=otbr_addon_manager.addon_slug)],
    )


async def guess_hardware_owners(
    hass: HomeAssistant, device_path: str
) -> list[FirmwareInfo]:
    """Guess the firmware info based on installed addons and other integrations."""
    device_guesses: defaultdict[str, list[FirmwareInfo]] = defaultdict(list)

    async for firmware_info in hass.data[DATA_COMPONENT].iter_firmware_info():
        device_guesses[firmware_info.device].append(firmware_info)

    # It may be possible for the OTBR addon to be present without the integration
    if is_hassio(hass):
        otbr_addon_manager = get_otbr_addon_manager(hass)
        otbr_addon_fw_info = await get_otbr_addon_firmware_info(
            hass, otbr_addon_manager
        )
        otbr_path = (
            otbr_addon_fw_info.device if otbr_addon_fw_info is not None else None
        )

        # Only create a new entry if there are no existing OTBR ones
        if otbr_path is not None and not any(
            info.source == "otbr" for info in device_guesses[otbr_path]
        ):
            assert otbr_addon_fw_info is not None
            device_guesses[otbr_path].append(otbr_addon_fw_info)

    if is_hassio(hass):
        multipan_addon_manager = await get_multiprotocol_addon_manager(hass)

        try:
            multipan_addon_info = await multipan_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if multipan_addon_info.state != AddonState.NOT_INSTALLED:
                multipan_path = multipan_addon_info.options.get("device")

                if multipan_path is not None:
                    device_guesses[multipan_path].append(
                        FirmwareInfo(
                            device=multipan_path,
                            firmware_type=ApplicationType.CPC,
                            firmware_version=None,
                            source="multiprotocol",
                            owners=[
                                OwningAddon(slug=multipan_addon_manager.addon_slug)
                            ],
                        )
                    )

    return device_guesses.get(device_path, [])


async def guess_firmware_info(hass: HomeAssistant, device_path: str) -> FirmwareInfo:
    """Guess the firmware type based on installed addons and other integrations."""

    hardware_owners = await guess_hardware_owners(hass, device_path)

    # Fall back to EZSP if we have no way to guess
    if not hardware_owners:
        return FirmwareInfo(
            device=device_path,
            firmware_type=ApplicationType.EZSP,
            firmware_version=None,
            source="unknown",
            owners=[],
        )

    # Prioritize guesses that are pulled from a real source
    guesses = [
        (guess, sum([await owner.is_running(hass) for owner in guess.owners]))
        for guess in hardware_owners
    ]
    guesses.sort(key=lambda p: p[1])
    assert guesses

    # Pick the best one. We use a stable sort so ZHA < OTBR < multi-PAN
    return guesses[-1][0]


async def probe_silabs_firmware_info(
    device: str,
    *,
    bootloader_reset_methods: Sequence[ResetTarget],
    application_probe_methods: Sequence[tuple[ApplicationType, int]],
) -> FirmwareInfo | None:
    """Probe the running firmware on a SiLabs device."""
    flasher = Flasher(
        device=device,
        probe_methods=tuple(
            (m.as_flasher_application_type(), baudrate)
            for m, baudrate in application_probe_methods
        ),
        bootloader_reset=tuple(
            m.as_flasher_reset_target() for m in bootloader_reset_methods
        ),
    )

    try:
        await flasher.probe_app_type()
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Failed to probe application type", exc_info=True)

    if flasher.app_type is None:
        return None

    return FirmwareInfo(
        device=device,
        firmware_type=ApplicationType.from_flasher_application_type(flasher.app_type),
        firmware_version=(
            flasher.app_version.orig_version
            if flasher.app_version is not None
            else None
        ),
        source="probe",
        owners=[],
    )


async def probe_silabs_firmware_type(
    device: str,
    *,
    bootloader_reset_methods: Sequence[ResetTarget],
    application_probe_methods: Sequence[tuple[ApplicationType, int]],
) -> ApplicationType | None:
    """Probe the running firmware type on a SiLabs device."""

    fw_info = await probe_silabs_firmware_info(
        device,
        bootloader_reset_methods=bootloader_reset_methods,
        application_probe_methods=application_probe_methods,
    )
    if fw_info is None:
        return None

    return fw_info.firmware_type


@asynccontextmanager
async def async_firmware_flashing_context(
    hass: HomeAssistant, device: str, source_domain: str
) -> AsyncIterator[None]:
    """Register a device as having its firmware being actively interacted with."""
    async with async_firmware_update_context(hass, device, source_domain):
        firmware_info = await guess_firmware_info(hass, device)
        _LOGGER.debug("Guessed firmware info before update: %s", firmware_info)

        async with AsyncExitStack() as stack:
            for owner in firmware_info.owners:
                await stack.enter_async_context(owner.temporarily_stop(hass))

            yield


async def async_flash_silabs_firmware(
    hass: HomeAssistant,
    device: str,
    fw_data: bytes,
    expected_installed_firmware_type: ApplicationType,
    bootloader_reset_methods: Sequence[ResetTarget],
    application_probe_methods: Sequence[tuple[ApplicationType, int]],
    progress_callback: Callable[[int, int], None] | None = None,
) -> FirmwareInfo:
    """Flash firmware to the SiLabs device.

    This function is meant to be used within a firmware update context.
    """
    if not any(
        method == expected_installed_firmware_type
        for method, _ in application_probe_methods
    ):
        raise ValueError(
            f"Expected installed firmware type {expected_installed_firmware_type!r}"
            f" not in application probe methods {application_probe_methods!r}"
        )

    fw_image = await hass.async_add_executor_job(parse_firmware_image, fw_data)

    flasher = Flasher(
        device=device,
        probe_methods=tuple(
            (m.as_flasher_application_type(), baudrate)
            for m, baudrate in application_probe_methods
        ),
        bootloader_reset=tuple(
            m.as_flasher_reset_target() for m in bootloader_reset_methods
        ),
    )

    try:
        # Enter the bootloader with indeterminate progress
        await flasher.enter_bootloader()

        # Flash the firmware, with progress
        await flasher.flash_firmware(fw_image, progress_callback=progress_callback)
    except PermissionError as err:
        raise HomeAssistantError(
            "Failed to flash firmware: Device is used by another application"
        ) from err
    except Exception as err:
        raise HomeAssistantError("Failed to flash firmware") from err

    probed_firmware_info = await probe_silabs_firmware_info(
        device,
        bootloader_reset_methods=bootloader_reset_methods,
        # Only probe for the expected installed firmware type
        application_probe_methods=[
            (method, baudrate)
            for method, baudrate in application_probe_methods
            if method == expected_installed_firmware_type
        ],
    )

    if probed_firmware_info is None:
        raise HomeAssistantError("Failed to probe the firmware after flashing")

    return probed_firmware_info
