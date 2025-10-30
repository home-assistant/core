"""The Seko Pooldose integration."""

from __future__ import annotations

import logging

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import PooldoseConfigEntry, PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PooldoseConfigEntry) -> bool:
    """Set up Seko PoolDose from a config entry."""
    # Get host from config entry data (connection-critical configuration)
    host = entry.data[CONF_HOST]

    # Create the PoolDose API client and connect
    client = PooldoseClient(host)
    try:
        client_status = await client.connect()
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout connecting to PoolDose device: {err}"
        ) from err
    except (ConnectionError, OSError) as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to PoolDose device: {err}"
        ) from err

    if client_status != RequestStatus.SUCCESS:
        raise ConfigEntryNotReady(
            f"Failed to create PoolDose client while initialization: {client_status}"
        )

    # Create coordinator and perform first refresh
    coordinator = PooldoseCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PooldoseConfigEntry) -> bool:
    """Unload the Seko PoolDose entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
