"""Arcam component."""

import asyncio
from asyncio import timeout
from contextlib import AsyncExitStack
import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import Client

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_SCAN_INTERVAL
from .coordinator import ArcamFmjConfigEntry, ArcamFmjCoordinator, ArcamFmjRuntimeData

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.BINARY_SENSOR, Platform.MEDIA_PLAYER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ArcamFmjConfigEntry) -> bool:
    """Set up config entry."""
    client = Client(entry.data[CONF_HOST], entry.data[CONF_PORT])

    coordinators: dict[int, ArcamFmjCoordinator] = {}
    for zone in (1, 2):
        coordinator = ArcamFmjCoordinator(hass, entry, client, zone)
        coordinators[zone] = coordinator

    entry.runtime_data = ArcamFmjRuntimeData(client, coordinators)

    entry.async_create_background_task(
        hass,
        _run_client(hass, entry.runtime_data, DEFAULT_SCAN_INTERVAL),
        "arcam_fmj",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArcamFmjConfigEntry) -> bool:
    """Cleanup before removing config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _run_client(
    hass: HomeAssistant,
    runtime_data: ArcamFmjRuntimeData,
    interval: float,
) -> None:
    client = runtime_data.client
    coordinators = runtime_data.coordinators

    while True:
        try:
            async with AsyncExitStack() as stack:
                async with timeout(interval):
                    await client.start()
                stack.push_async_callback(client.stop)

                _LOGGER.debug("Client connected %s", client.host)

                try:
                    for coordinator in coordinators.values():
                        await stack.enter_async_context(
                            coordinator.async_monitor_client()
                        )

                    await client.process()
                finally:
                    _LOGGER.debug("Client disconnected %s", client.host)

        except ConnectionFailed:
            pass
        except TimeoutError:
            continue
        except Exception:
            _LOGGER.exception("Unexpected exception, aborting arcam client")
            return

        await asyncio.sleep(interval)
