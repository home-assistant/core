"""The Seko Pooldose integration."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .coordinator import PooldoseConfigEntry, PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_migrate_entry(hass: HomeAssistant, entry: PooldoseConfigEntry) -> bool:
    """Migrate old entry."""
    # Version 1.1 -> 1.2: Migrate entity unique IDs
    # - ofa_orp_value -> ofa_orp_time
    # - ofa_ph_value -> ofa_ph_time
    if entry.version == 1 and entry.minor_version < 2:

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
            """Migrate entity unique IDs for pooldose sensors."""
            new_unique_id = entity_entry.unique_id

            # Check if this entry needs migration
            if "_ofa_orp_value" in new_unique_id:
                new_unique_id = new_unique_id.replace("_ofa_orp_value", "_ofa_orp_time")
            elif "_ofa_ph_value" in new_unique_id:
                new_unique_id = new_unique_id.replace("_ofa_ph_value", "_ofa_ph_time")
            else:
                # No migration needed
                return None

            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

        hass.config_entries.async_update_entry(entry, version=1, minor_version=2)

    return True


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
