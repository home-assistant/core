"""Integration for all haus-bus.de modules."""

import contextlib
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .gateway import HausbusGateway, HomeServerUnavailable, async_release_home_server

PLATFORMS: list[Platform] = [
    Platform.COVER,
]

LOGGER = logging.getLogger(__name__)


type HausbusConfigEntry = ConfigEntry[HausbusGateway]


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> None:
    """Set up Haus-Bus integration from a config entry."""
    try:
        gateway = await HausbusGateway.async_create(hass, entry)
    except HomeServerUnavailable as err:
        # Terminal until Home Assistant restarts, retrying cannot succeed.
        raise ConfigEntryError(str(err)) from err
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

    await gateway.async_flush_pending_channels()

    # Discovery is a best-effort broadcast, so setup does not block on it.
    gateway.discovery_task = entry.async_create_background_task(
        hass, gateway.start_discovery(), "Haus-Bus discovery"
    )


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> None:
    """Unload a config entry."""
    gateway = entry.runtime_data
    if gateway.discovery_task is not None:
        with contextlib.suppress(Exception):
            await gateway.discovery_task

    # removeBusDeviceListener() cannot recall callbacks already queued on the
    # event loop, so also buffer new channels until the platform is unloaded.
    gateway.pause_channel_dispatch()
    gateway.home_server.removeBusDeviceListener(gateway)
    try:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    except BaseException:
        gateway.home_server.addBusDeviceListener(gateway)
        await gateway.async_flush_pending_channels()
        raise

    gateway.home_server.removeBusEventListener(gateway)

    # A failed shutdown is terminal, see async_release_home_server.
    try:
        await async_release_home_server(hass, gateway.home_server)
    except Exception:
        LOGGER.exception("Failed to cleanly shut down the Haus-Bus network connection")
