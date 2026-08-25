"""Integration for all haus-bus.de modules."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .gateway import HausbusGateway

PLATFORMS: list[Platform] = [
    Platform.COVER,
]

LOGGER = logging.getLogger(__name__)


type HausbusConfigEntry = ConfigEntry[HausbusGateway]


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus integration from a config entry."""
    try:
        gateway = await HausbusGateway.async_create(hass, entry)
    except OSError as err:
        raise ConfigEntryNotReady(
            "Unable to open the Haus-Bus network connection"
        ) from err

    entry.runtime_data = gateway

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        gateway.home_server.removeBusEventListener(gateway)
        gateway.home_server.removeBusDeviceListener(gateway)
        await hass.async_add_executor_job(gateway.home_server.shutdown)
        raise

    # Start device discovery in the background: it is a best-effort UDP
    # broadcast that may find devices at any time, not only at startup, so
    # setup does not block on it. Cancel it on unload/reload so a still
    # running search does not keep using a torn-down gateway.
    discovery_task = hass.async_create_task(gateway.start_discovery())

    def _cancel_discovery() -> None:
        discovery_task.cancel()

    entry.async_on_unload(_cancel_discovery)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data
    # Only deregister the gateway's pyhausbus listeners once the platforms
    # have actually unloaded. pyhausbus removes listeners via list.remove(),
    # which raises if called twice, so deregistering unconditionally here
    # would break a retry after a failed platform unload.
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        gateway.home_server.removeBusEventListener(gateway)
        gateway.home_server.removeBusDeviceListener(gateway)
        # manifest.json sets single_config_entry, so this is always the
        # only config entry using the process-wide HomeServer singleton -
        # it is exclusively ours to tear down. Otherwise its UDP listener
        # and worker/collector threads would keep running indefinitely
        # after unload. Runs in the executor since shutdown() joins those
        # threads (blocking). Drop the cached reference too, so a reload
        # builds a genuinely fresh HomeServer instead of reusing the one
        # that was just shut down.
        await hass.async_add_executor_job(gateway.home_server.shutdown)
    return unload_ok
