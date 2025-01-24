"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import cast

from universal_silabs_flasher.const import ApplicationType as FlasherApplicationType
from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.singleton import singleton

from .const import (
    OTBR_ADDON_MANAGER_DATA,
    OTBR_ADDON_NAME,
    OTBR_ADDON_SLUG,
    ZHA_DOMAIN,
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


def get_zha_device_path(config_entry: ConfigEntry) -> str | None:
    """Get the device path from a ZHA config entry."""
    return cast(str | None, config_entry.data.get("device", {}).get("path", None))


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


@dataclass(slots=True, kw_only=True)
class FirmwareGuess:
    """Firmware guess."""

    is_running: bool
    firmware_type: ApplicationType
    source: str


async def guess_firmware_type(hass: HomeAssistant, device_path: str) -> FirmwareGuess:
    """Guess the firmware type based on installed addons and other integrations."""
    device_guesses: defaultdict[str | None, list[FirmwareGuess]] = defaultdict(list)

    for zha_config_entry in hass.config_entries.async_entries(ZHA_DOMAIN):
        zha_path = get_zha_device_path(zha_config_entry)

        if zha_path is not None:
            device_guesses[zha_path].append(
                FirmwareGuess(
                    is_running=(zha_config_entry.state == ConfigEntryState.LOADED),
                    firmware_type=ApplicationType.EZSP,
                    source="zha",
                )
            )

    if is_hassio(hass):
        otbr_addon_manager = get_otbr_addon_manager(hass)

        try:
            otbr_addon_info = await otbr_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if otbr_addon_info.state != AddonState.NOT_INSTALLED:
                otbr_path = otbr_addon_info.options.get("device")
                device_guesses[otbr_path].append(
                    FirmwareGuess(
                        is_running=(otbr_addon_info.state == AddonState.RUNNING),
                        firmware_type=ApplicationType.SPINEL,
                        source="otbr",
                    )
                )

        multipan_addon_manager = await get_multiprotocol_addon_manager(hass)

        try:
            multipan_addon_info = await multipan_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if multipan_addon_info.state != AddonState.NOT_INSTALLED:
                multipan_path = multipan_addon_info.options.get("device")
                device_guesses[multipan_path].append(
                    FirmwareGuess(
                        is_running=(multipan_addon_info.state == AddonState.RUNNING),
                        firmware_type=ApplicationType.CPC,
                        source="multiprotocol",
                    )
                )

    # Fall back to EZSP if we can't guess the firmware type
    if device_path not in device_guesses:
        return FirmwareGuess(
            is_running=False, firmware_type=ApplicationType.EZSP, source="unknown"
        )

    # Prioritizes guesses that were pulled from a running addon or integration but keep
    # the sort order we defined above
    guesses = sorted(
        device_guesses[device_path],
        key=lambda guess: guess.is_running,
    )

    assert guesses

    return guesses[-1]


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
