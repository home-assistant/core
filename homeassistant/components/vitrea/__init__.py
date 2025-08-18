"""The vitrea integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

from vitreaclient import DeviceStatus, VitreaClient, VitreaResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

# Import entity classes - these are used at runtime in the setup function
from .cover import VitreaCover
from .number import VitreaTimerControl
from .switch import VitreaSwitch

_LOGGER = logging.getLogger(__name__)

# List the platforms that you want to support.
_PLATFORMS = [Platform.SWITCH, Platform.COVER, Platform.NUMBER]


@dataclass
class VitreaRuntimeData:
    """Runtime data for Vitrea integration."""

    client: VitreaClient
    covers: list[VitreaCover]
    switches: list[VitreaSwitch]
    timers: list[VitreaTimerControl]


type VitreaConfigEntry = ConfigEntry[VitreaRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Set up vitrea from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    try:
        _LOGGER.debug(
            "Connecting to Vitrea box at %s:%s with config: %s", host, port, entry.data
        )
        monitor = VitreaClient(host, port)

        # Test connection before proceeding with setup
        await monitor.connect()

        # Initialize runtime data with the client and empty entity lists
        entry.runtime_data = VitreaRuntimeData(
            client=monitor, covers=[], switches=[], timers=[]
        )

        entities = set()

        def handle_new_entity(event) -> None:
            """Register entities sent by vitrea box upon status request."""
            entity_id = f"{event.node}_{event.key}"
            if entity_id in entities:
                return
            if event.status == DeviceStatus.BLIND:
                entities.add(entity_id)
                _LOGGER.debug("New cover discovered: %s", entity_id)
                entry.runtime_data.covers.append(
                    VitreaCover(event.node, event.key, event.data, monitor)
                )

            elif event.status in (DeviceStatus.SWITCH_ON, DeviceStatus.SWITCH_OFF):
                _LOGGER.debug("New switch discovered: %s", entity_id)
                entities.add(entity_id)
                entry.runtime_data.switches.append(
                    VitreaSwitch(
                        event.node,
                        event.key,
                        event.status == DeviceStatus.SWITCH_ON,
                        monitor,
                    )
                )
            elif event.status in (DeviceStatus.BOILER_ON, DeviceStatus.BOILER_OFF):
                _LOGGER.debug("New boiler discovered: %s", entity_id)
                entities.add(entity_id)
                timer_control = VitreaTimerControl(
                    event.node, event.key, event.data, monitor
                )
                entry.runtime_data.timers.append(timer_control)
                entry.runtime_data.switches.append(
                    VitreaSwitch(
                        event.node,
                        event.key,
                        event.status == DeviceStatus.BOILER_ON,
                        monitor,
                        timer_control,
                    )
                )

        monitor.on(VitreaResponse.STATUS, handle_new_entity)
        await monitor.start_read_task()
        await monitor.status_request()

        # Vitrea sends slowly the status response for each node/key
        # we wait as long as entities are being discovered, assuming that
        # a lack of change in 10 seconds means that no more entities are being discovered
        entity_count = 0
        max_discovery_time = 120
        discovery_start = time.monotonic()
        while True:
            await asyncio.sleep(10)
            if len(entities) == entity_count:
                break
            if time.monotonic() - discovery_start > max_discovery_time:
                _LOGGER.warning(
                    "Entity discovery timed out after %d seconds. Proceeding with %d entities: %s",
                    max_discovery_time,
                    len(entities),
                    entities,
                )
                break
            entity_count = len(entities)

        monitor.off(VitreaResponse.STATUS, handle_new_entity)
        _LOGGER.debug("Discovered %d entities: %s", len(entities), entities)

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

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if unload_ok:
        # Clean up the monitor and any resources from runtime_data
        if hasattr(entry.runtime_data.client, "disconnect"):
            await entry.runtime_data.client.disconnect()

    return unload_ok
