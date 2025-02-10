"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
import logging

from universal_silabs_flasher.const import ApplicationType as FlasherApplicationType
from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
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
from .silabs_multiprotocol_addon import (
    WaitingAddonManager,
    get_multiprotocol_addon_manager,
)

_LOGGER = logging.getLogger(__name__)


class ApplicationType(StrEnum):
    """Application type running on a device."""

    GECKO_BOOTLOADER = "bootloader"
    CPC = "cpc"
    EZSP = "ezsp"
    SPINEL = "spinel"

    @classmethod
    def from_flasher_application_type(
        cls, app_type: FlasherApplicationType
    ) -> ApplicationType:
        """Convert a USF application type enum."""
        return cls(app_type.value)

    def as_flasher_application_type(self) -> FlasherApplicationType:
        """Convert the application type enum into one compatible with USF."""
        return FlasherApplicationType(self.value)


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

        try:
            otbr_addon_info = await otbr_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if otbr_addon_info.state != AddonState.NOT_INSTALLED:
                otbr_path = otbr_addon_info.options.get("device")

                # Only create a new entry if there are no existing OTBR ones
                if otbr_path is not None and not any(
                    info.source == "otbr" for info in device_guesses[otbr_path]
                ):
                    device_guesses[otbr_path].append(
                        FirmwareInfo(
                            device=otbr_path,
                            firmware_type=ApplicationType.SPINEL,
                            firmware_version=None,
                            source="otbr",
                            owners=[OwningAddon(slug=otbr_addon_manager.addon_slug)],
                        )
                    )

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


async def probe_silabs_firmware_type(
    device: str, *, probe_methods: Iterable[ApplicationType] | None = None
) -> ApplicationType | None:
    """Probe the running firmware on a Silabs device."""
    flasher = Flasher(
        device=device,
        **(
            {"probe_methods": [m.as_flasher_application_type() for m in probe_methods]}
            if probe_methods
            else {}
        ),
    )

    try:
        await flasher.probe_app_type()
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Failed to probe application type", exc_info=True)

    if flasher.app_type is None:
        return None

    return ApplicationType.from_flasher_application_type(flasher.app_type)
