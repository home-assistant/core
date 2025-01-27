"""Home Assistant Hardware firmware utilities."""

from __future__ import annotations

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningIntegration,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helpers import get_zha_gateway


async def get_firmware_info(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> FirmwareInfo | None:
    """Return firmware information for the ZHA instance."""

    # We only support EZSP firmware for now
    if config_entry.data.get("radio_type", None) != "ezsp":
        return None

    device = config_entry.data.get("device", {}).get("path", None)
    if device is None:
        return None

    try:
        gateway = get_zha_gateway(hass)
    except ValueError:
        firmware_version = None
    else:
        firmware_version = gateway.state.node_info.version

    return FirmwareInfo(
        device=device,
        firmware_type=ApplicationType.EZSP,
        firmware_version=firmware_version,
        source=DOMAIN,
        owners=[OwningIntegration(config_entry_id=config_entry.entry_id)],
    )
