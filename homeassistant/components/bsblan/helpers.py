"""Helper functions for BSB-Lan integration."""

from __future__ import annotations

from bsblan import BSBLAN, BSBLANError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_sync_device_time(client: BSBLAN, device_name: str) -> None:
    """Synchronize BSB-LAN device time with Home Assistant.

    Only updates if device time differs from Home Assistant time.

    Args:
        client: The BSB-LAN client instance.
        device_name: The name of the device (used in error messages).

    Raises:
        HomeAssistantError: If the time sync operation fails.

    """
    try:
        device_time = await client.time()
        current_time = dt_util.now()
        current_time_str = current_time.strftime("%d.%m.%Y %H:%M:%S")

        # Only sync if device time differs from HA time
        if device_time.time.value != current_time_str:
            await client.set_time(current_time_str)
    except BSBLANError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="sync_time_failed",
            translation_placeholders={
                "device_name": device_name,
                "error": str(err),
            },
        ) from err
