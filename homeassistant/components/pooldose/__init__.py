"""The Seko Pooldose integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class PooldoseRuntimeData:
    """Runtime data for Pooldose integration."""

    client: PooldoseClient
    coordinator: PooldoseCoordinator
    device_properties: dict[str, str | None]


type PooldoseConfigEntry = ConfigEntry[PooldoseRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: PooldoseConfigEntry) -> bool:
    """Set up Seko PoolDose from a config entry."""
    # Get host from config entry data (connection-critical configuration)
    host = entry.data[CONF_HOST]

    # Create the PoolDose API client and connect
    client = PooldoseClient(host)
    client_status = await client.connect()
    if client_status != RequestStatus.SUCCESS:
        _LOGGER.error("Failed to create PoolDose client: %s", client_status)
        raise ConfigEntryNotReady(f"Failed to create PoolDose client: {client_status}")

    # Create coordinator and perform first refresh
    coordinator = PooldoseCoordinator(hass, client, timedelta(seconds=600), entry)
    await coordinator.async_config_entry_first_refresh()

    # Get device info from client after successful connection
    device_properties = client.device_info

    # Store runtime data
    entry.runtime_data = PooldoseRuntimeData(
        client=client,
        coordinator=coordinator,
        device_properties=device_properties,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PooldoseConfigEntry) -> bool:
    """Unload the Seko PoolDose entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
