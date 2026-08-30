"""Integration for all haus-bus.de modules."""

import contextlib
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .gateway import HausbusGateway, async_release_home_server

PLATFORMS: list[Platform] = [
    Platform.COVER,
]

LOGGER = logging.getLogger(__name__)


type HausbusConfigEntry = ConfigEntry[HausbusGateway]


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus integration from a config entry."""
    try:
        gateway = await HausbusGateway.async_create(hass, entry)
    except (OSError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            "Unable to open the Haus-Bus network connection"
        ) from err

    entry.runtime_data = gateway

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        gateway.home_server.removeBusEventListener(gateway)
        gateway.home_server.removeBusDeviceListener(gateway)
        await async_release_home_server(hass, gateway.home_server)
        raise

    # Flush channels discovered while the platform was still setting up.
    await gateway.async_flush_pending_channels()

    # Start device discovery in the background: it is a best-effort UDP
    # broadcast that may find devices at any time, not only at startup, so
    # setup does not block on it. The task is stored on the gateway so
    # async_unload_entry can await it before tearing down the HomeServer
    # singleton; if it is still running by then, the config entry
    # framework cancels it once async_unload_entry returns.
    gateway.discovery_task = entry.async_create_background_task(
        hass, gateway.start_discovery(), "Haus-Bus discovery"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data
    if gateway.discovery_task is not None:
        with contextlib.suppress(Exception):
            await gateway.discovery_task

    # Stop delivering newly discovered devices before unloading the cover
    # platform below. pyhausbus's DeviceWorker thread can still be
    # processing in-flight search replies after searchDevices() (and
    # discovery_task above) return, and the cover platform's
    # NEW_CHANNEL_ADDED dispatcher listener - registered via
    gateway.pause_channel_dispatch()
    gateway.home_server.removeBusDeviceListener(gateway)
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except BaseException:
        gateway.home_server.addBusDeviceListener(gateway)
        await gateway.async_flush_pending_channels()
        raise
    if not unload_ok:
        gateway.home_server.addBusDeviceListener(gateway)
        await gateway.async_flush_pending_channels()
        return unload_ok

    gateway.home_server.removeBusEventListener(gateway)

    # HomeServer is a process-wide singleton that an in-progress config
    # flow can also be holding a reference to (see
    # gateway.async_acquire_home_server), so release our reference
    # rather than shutting it down unconditionally here - it is only
    # actually shut down once nothing else still needs it. Otherwise
    # its UDP listener and worker/collector threads would keep running
    # indefinitely after unload.
    #
    # This can raise RuntimeError if a worker/collector thread was too
    # slow to stop (see gateway.async_release_home_server) - by design,
    # so that failure is surfaced rather than reported as a successful
    # unload, rather than silently leaving a stray thread running. HA
    # core marks the resulting FAILED_UNLOAD state as non-recoverable
    # (see ConfigEntryState in homeassistant/config_entries.py):
    # async_unload()/async_setup()/async_remove() all refuse to touch
    # the entry again afterwards, so this function is never re-entered
    # for the same entry - the only way out is restarting Home
    # Assistant, which starts a fresh process with a fresh gateway and
    # HomeServer, not a second call here.
    await async_release_home_server(hass, gateway.home_server)
    return unload_ok
