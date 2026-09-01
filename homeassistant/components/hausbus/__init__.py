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
    # async_unload_entry can await it to completion before tearing down
    # the HomeServer singleton.
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

    # Gate dispatch before touching the pyhausbus listener:
    # removeBusDeviceListener() cannot recall a newDeviceDetected() call
    # already in flight or already queued onto the event loop, and the
    # cover platform's NEW_CHANNEL_ADDED listener is not disconnected
    # until this function returns successfully - so a late callback could
    # still call async_add_entities() on a mid-teardown platform.
    # gateway.pause_channel_dispatch() (see its docstring) closes that
    # gap; both it and the listener removal are undone if the platform
    # unload fails.
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

    # Release the process-wide HomeServer reference. A shutdown failure is terminal
    # because pyhausbus already reset its singleton, so block future acquisitions.
    try:
        await async_release_home_server(hass, gateway.home_server)
    except Exception:
        LOGGER.exception("Failed to cleanly shut down the Haus-Bus network connection")
    return unload_ok
