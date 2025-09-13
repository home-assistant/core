"""The vitrea integration."""

from __future__ import annotations

import asyncio
import logging
import time

from vitreaclient import DeviceStatus, VitreaClient, VitreaResponse

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import MAX_DISCOVERY_TIME, SLEEP_INTERVAL

# Import entity classes - only cover for simplified integration
from .cover import VitreaCover
from .models import VitreaConfigEntry, VitreaRuntimeData

_LOGGER = logging.getLogger(__name__)

# List the platforms that you want to support - only cover for new integration
_PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Set up vitrea from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    _LOGGER.debug(
        "Connecting to Vitrea box at %s:%s with config: %s", host, port, entry.data
    )

    try:
        monitor = VitreaClient(host, port)

        # Initialize runtime data with the client and empty entity lists
        entry.runtime_data = VitreaRuntimeData(client=monitor, covers=[])

        entities = set()

        def handle_new_entity(event) -> None:
            """Register cover entities sent by vitrea box upon status request."""
            entity_id = f"{event.node}_{event.key}"
            if entity_id in entities:
                return
            # Only discover cover/blind entities for simplified integration
            if event.status == DeviceStatus.BLIND:
                entities.add(entity_id)
                _LOGGER.debug("New cover discovered: %s", entity_id)
                entry.runtime_data.covers.append(
                    VitreaCover(event.node, event.key, event.data, monitor)
                )

        monitor.on(VitreaResponse.STATUS, handle_new_entity)

        await monitor.connect()

        # Request status to discover entities
        await monitor.status_request()

        # Optimized discovery: shorter wait times for faster startup
        # Vitrea sends slowly the status response for each node/key
        # we wait as long as entities are being discovered, but with shorter intervals
        entity_count = 0
        discovery_start = time.monotonic()

        while True:
            await asyncio.sleep(SLEEP_INTERVAL)

            if len(entities) == entity_count:
                # No new entities discovered in this cycle - discovery likely complete
                break

            if time.monotonic() - discovery_start > MAX_DISCOVERY_TIME:
                _LOGGER.warning(
                    "Entity discovery timed out after %d seconds. Proceeding with %d entities: %s",
                    MAX_DISCOVERY_TIME,
                    len(entities),
                    entities,
                )
                break

            entity_count = len(entities)

        monitor.off(VitreaResponse.STATUS, handle_new_entity)
        _LOGGER.info(
            "Vitrea integration setup complete. Discovered %d cover entities: %s",
            len(entities),
            entities,
        )
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    except ConnectionError as ex:
        # Connection failed - device may be offline or unreachable
        raise ConfigEntryNotReady(
            f"Failed to connect to Vitrea at {host}:{port}"
        ) from ex
    except TimeoutError as ex:
        # Connection timeout - device may be slow to respond
        raise ConfigEntryNotReady(
            f"Timeout connecting to Vitrea at {host}:{port}"
        ) from ex
    except Exception as ex:
        # Unexpected error during setup
        _LOGGER.exception("Unexpected error setting up Vitrea integration")
        raise ConfigEntryError(f"Unknown error connecting to Vitrea: {ex}") from ex

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    # Only clean up if runtime_data exists
    runtime_data = getattr(entry, "runtime_data", None)
    if unload_ok and runtime_data is not None:
        if hasattr(runtime_data.client, "disconnect"):
            try:
                await runtime_data.client.disconnect()
            except (ConnectionError, TimeoutError) as ex:
                _LOGGER.warning("Error disconnecting Vitrea client: %s", ex)

    return unload_ok
