"""The Connector integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from socket import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .connector_local import WIFIMOTORTYPE, ConnectorHub
from .const import (
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    KEY_MULTICAST_LISTENER,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["cover"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up connector from a config entry."""
    # time.sleep(5)
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]
    connector = ConnectorHub(ip=host, key=key)

    if KEY_MULTICAST_LISTENER not in hass.data[DOMAIN]:
        connector.start_receive_data()
        # multicast = connector
        hass.data[DOMAIN][KEY_MULTICAST_LISTENER] = connector

        # register stop callback to shutdown listening for local pushes
        def stop_motion_multicast(event):
            """Stop multicast thread."""
            _LOGGER.debug("Shutting down Connector Listener")
            connector.close_receive_data()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_motion_multicast)

    def update_gateway():
        """Call all updates using one async_add_executor_job."""
        for device in connector.device_list().values():
            try:
                device.update_blinds()
            except timeout:
                _LOGGER.warning("Update gateway timeout")

    async def async_update_data():
        """Fetch data from the gateway and blinds."""
        try:
            await hass.async_add_executor_job(update_gateway)
        except timeout:
            _LOGGER.warning("Async update data timeout")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_GATEWAY: connector,
        KEY_COORDINATOR: coordinator,
    }

    device_registry = dr.async_get(hass)
    # Need wait 3S then to get deviceList
    await asyncio.sleep(3)
    device_list = connector.device_list()
    for hub in device_list.values():
        if hub.devicetype not in WIFIMOTORTYPE:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={(dr.CONNECTION_NETWORK_MAC, hub.hub_mac)},
                identifiers={(DOMAIN, hub.hub_mac)},
                manufacturer=MANUFACTURER,
                name=entry.title,
                model="Wi-Fi bridge",
                sw_version=hub.hub_version,
            )
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # hass.data[DOMAIN][entry.entry_id][KEY_GATEWAY].close_receive_data()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    if len(hass.data[DOMAIN]) == 1:
        _LOGGER.debug("Shutting down Connector Listener")
        multicast = hass.data[DOMAIN].pop(KEY_MULTICAST_LISTENER)
        await hass.async_add_executor_job(multicast.close_receive_data)
    return unload_ok
