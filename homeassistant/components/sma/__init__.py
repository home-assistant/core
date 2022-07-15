"""The sma integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import pysma

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GROUP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    PYSMA_COORDINATOR,
    PYSMA_DEVICE_INFO,
    PYSMA_OBJECT,
    PYSMA_REMOVE_LISTENER,
    PYSMA_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up sma from a config entry."""
    # Init the SMA interface
    protocol = "https" if entry.data[CONF_SSL] else "http"
    url = f"{protocol}://{entry.data[CONF_HOST]}"
    verify_ssl = entry.data[CONF_VERIFY_SSL]
    group = entry.data[CONF_GROUP]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    sma = pysma.SMA(session, url, password, group)

    try:
        # Get updated device info
        sma_device_info = await sma.device_info()
        # Get all device sensors
        sensor_def = await sma.get_sensors()
    except (
        pysma.exceptions.SmaReadException,
        pysma.exceptions.SmaConnectionException,
    ) as exc:
        raise ConfigEntryNotReady from exc

    if TYPE_CHECKING:
        assert entry.unique_id

    # Create DeviceInfo object from sma_device_info
    device_info = DeviceInfo(
        configuration_url=url,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=sma_device_info["manufacturer"],
        model=sma_device_info["type"],
        name=sma_device_info["name"],
        sw_version=sma_device_info["sw_version"],
    )

    # Define the coordinator
    async def async_update_data():
        """Update the used SMA sensors."""
        try:
            await sma.read(sensor_def)
        except (
            pysma.exceptions.SmaReadException,
            pysma.exceptions.SmaConnectionException,
        ) as exc:
            raise UpdateFailed(exc) from exc

    interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sma",
        update_method=async_update_data,
        update_interval=interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await sma.close_session()
        raise

    # Ensure we logout on shutdown
    async def async_close_session(event):
        """Close the session."""
        await sma.close_session()

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_close_session
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        PYSMA_OBJECT: sma,
        PYSMA_COORDINATOR: coordinator,
        PYSMA_SENSORS: sensor_def,
        PYSMA_REMOVE_LISTENER: remove_stop_listener,
        PYSMA_DEVICE_INFO: device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[PYSMA_OBJECT].close_session()
        data[PYSMA_REMOVE_LISTENER]()

    return unload_ok
