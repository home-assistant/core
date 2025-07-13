"""The Seko Pooldose integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pooldose.client import PooldoseClient
from pooldose.request_handler import RequestStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import SCAN_INTERVAL
from .coordinator import PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]

"""Configure the Seko PoolDose entry."""


async def async_update_device_info(client: PooldoseClient) -> dict[str, str | None]:
    """Fetch latest device info from all relevant endpoints."""
    device_info: dict[str, str | None] = {}
    if client.device_info is None:
        _LOGGER.error("Device info is not available from PoolDose client")
    else:
        device_info = client.device_info
    return device_info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Seko PoolDose from a config entry."""
    # Obtain values, preferring options (re‑configure) over static data
    host = entry.options.get(CONF_HOST, entry.data[CONF_HOST])

    # Create the PoolDose API client
    client_status, client = await PooldoseClient.create(host)
    if client_status != RequestStatus.SUCCESS:
        _LOGGER.error("Failed to create PoolDose client: %s", client_status)
        return False

    coordinator = PooldoseCoordinator(hass, client, timedelta(seconds=SCAN_INTERVAL))
    await coordinator.async_config_entry_first_refresh()

    # Update device info on every reload
    device_info = await async_update_device_info(client)

    hass.data.setdefault("pooldose", {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Seko PoolDose entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
