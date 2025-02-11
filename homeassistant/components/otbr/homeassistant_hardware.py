"""Home Assistant Hardware firmware utilities."""

from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol
from yarl import URL

from homeassistant.components.hassio import AddonManager, valid_addon
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
    get_otbr_addon_firmware_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.hassio import is_hassio

from . import OTBRConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_firmware_info(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> FirmwareInfo | None:
    """Return firmware information for the OpenThread Border Router."""
    owners: list[OwningIntegration | OwningAddon] = [
        OwningIntegration(config_entry_id=config_entry.entry_id)
    ]

    device = None

    if is_hassio(hass) and (host := URL(config_entry.data["url"]).host) is not None:
        try:
            valid_addon(host)
        except vol.Invalid:
            pass
        else:
            otbr_addon_manager = AddonManager(
                hass=hass,
                logger=_LOGGER,
                addon_name="OpenThread Border Router",
                addon_slug=host,
            )

            if (
                addon_fw_info := await get_otbr_addon_firmware_info(
                    hass, otbr_addon_manager
                )
            ) is not None:
                device = addon_fw_info.device
                owners.extend(addon_fw_info.owners)

    if config_entry.state == ConfigEntryState.LOADED:
        config_entry = cast(OTBRConfigEntry, config_entry)

        if device is None:
            device = config_entry.data.get("device", None)

        try:
            firmware_version = await config_entry.runtime_data.get_coprocessor_version()
        except HomeAssistantError:
            firmware_version = None

    if device is None:
        return None

    return FirmwareInfo(
        device=device,
        firmware_type=ApplicationType.SPINEL,
        firmware_version=firmware_version,
        source=DOMAIN,
        owners=owners,
    )
