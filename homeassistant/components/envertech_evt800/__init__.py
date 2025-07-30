"""Envertech EVT800 integration."""

from datetime import timedelta
import logging

import pyenvertechevt800

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENVERTECH_EVT800_COORDINATOR,
    ENVERTECH_EVT800_DEVICE_INFO,
    ENVERTECH_EVT800_OBJECT,
    ENVERTECH_EVT800_REMOVE_LISTENER,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Envertech EVT800 from a config entry."""
    coordinator = None

    def on_data(data):
        if coordinator:
            coordinator.async_set_updated_data(data)

    async def update_data():
        return None

    evt800 = pyenvertechevt800.EnvertechEVT800(
        entry.data[CONF_IP_ADDRESS], entry.data[CONF_PORT], on_data
    )
    entry.runtime_data = evt800

    evt800.start()

    device_info = DeviceInfo(
        identifiers={
            (
                DOMAIN,
                entry.unique_id
                or f"{entry.data[CONF_IP_ADDRESS]}-{entry.data[CONF_PORT]}",
            )
        },
        configuration_url=f"http://{entry.data[CONF_IP_ADDRESS]}/",
        manufacturer="Envertech",
        model="EVT800",
        name="Envertech EVT800",
        sw_version="1.0.0",
        serial_number=evt800.serial_number,
    )

    interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name="envertech_evt800",
        update_interval=interval,
        update_method=update_data,
    )
    coordinator.async_set_updated_data(evt800.data)

    await coordinator.async_config_entry_first_refresh()

    async def async_close_session(event):
        """Close the session."""
        await evt800.stop()

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_close_session
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ENVERTECH_EVT800_OBJECT: evt800,
        ENVERTECH_EVT800_COORDINATOR: coordinator,
        ENVERTECH_EVT800_REMOVE_LISTENER: remove_stop_listener,
        ENVERTECH_EVT800_DEVICE_INFO: device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if data[ENVERTECH_EVT800_OBJECT] is not None:
            await data[ENVERTECH_EVT800_OBJECT].stop()
        if data[ENVERTECH_EVT800_REMOVE_LISTENER] is not None:
            data[ENVERTECH_EVT800_REMOVE_LISTENER]()

    return unload_ok
