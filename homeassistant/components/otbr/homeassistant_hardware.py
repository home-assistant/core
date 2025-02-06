"""Home Assistant Hardware firmware utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import voluptuous as vol
from yarl import URL

from homeassistant.components.hassio import valid_addon
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.hassio import is_hassio

from .const import DOMAIN

if TYPE_CHECKING:
    from . import OTBRConfigEntry


async def async_get_firmware_info(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> FirmwareInfo | None:
    """Return firmware information for the OpenThread Border Router."""
    if TYPE_CHECKING:
        config_entry = cast(OTBRConfigEntry, config_entry)

    if (device := config_entry.data.get("device")) is None:
        return None

    owners: list[OwningIntegration | OwningAddon] = [
        OwningIntegration(config_entry_id=config_entry.entry_id)
    ]

    if is_hassio(hass) and (host := URL(config_entry.data["url"]).host) is not None:
        try:
            valid_addon(host)
        except vol.Invalid:
            pass
        else:
            owners.append(OwningAddon(slug=host))

    try:
        firmware_version = await config_entry.runtime_data.get_coprocessor_version()
    except HomeAssistantError:
        firmware_version = None

    return FirmwareInfo(
        device=device,
        firmware_type=ApplicationType.SPINEL,
        firmware_version=firmware_version,
        source=DOMAIN,
        owners=owners,
    )
