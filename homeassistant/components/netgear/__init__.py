"""Support for Netgear routers."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    KEY_COORDINATOR,
    KEY_COORDINATOR_TRAFFIC,
    KEY_ROUTER,
    PLATFORMS,
)
from .errors import CannotLoginException
from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netgear component."""
    router = NetgearRouter(hass, entry)
    try:
        if not await router.async_setup():
            raise ConfigEntryNotReady
    except CannotLoginException as ex:
        raise ConfigEntryNotReady from ex

    port = entry.data.get(CONF_PORT)
    ssl = entry.data.get(CONF_SSL)
    if port != router.port or ssl != router.ssl:
        data = {**entry.data, CONF_PORT: router.port, CONF_SSL: router.ssl}
        hass.config_entries.async_update_entry(entry, data=data)
        _LOGGER.info(
            "Netgear port-SSL combination updated from (%i, %r) to (%i, %r), "
            "this should only occur after a firmware update",
            port,
            ssl,
            router.port,
            router.ssl,
        )

    hass.data.setdefault(DOMAIN, {})

    entry.async_on_unload(entry.add_update_listener(update_listener))

    assert entry.unique_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Netgear",
        name=router.device_name,
        model=router.model,
        sw_version=router.firmware_version,
        hw_version=router.hardware_version,
        configuration_url=f"http://{entry.data[CONF_HOST]}/",
    )

    async def async_update_devices() -> bool:
        """Fetch data from the router."""
        return await router.async_update_device_trackers()

    async def async_update_traffic_meter() -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await router.async_get_traffic_meter()

    # Create update coordinators
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{router.device_name} Devices",
        update_method=async_update_devices,
        update_interval=SCAN_INTERVAL,
    )
    coordinator_traffic_meter = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{router.device_name} Traffic meter",
        update_method=async_update_traffic_meter,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()
    await coordinator_traffic_meter.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_ROUTER: router,
        KEY_COORDINATOR: coordinator,
        KEY_COORDINATOR_TRAFFIC: coordinator_traffic_meter,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
