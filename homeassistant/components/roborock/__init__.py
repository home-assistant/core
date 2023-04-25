"""The Roborock component."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from roborock.api import RoborockApiClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import HomeDataDevice, RoborockDeviceInfo, UserData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_BASE_URL, CONF_USER_DATA, DOMAIN, PLATFORMS
from .coordinator import RoborockDataUpdateCoordinator

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())

    user_data = UserData.from_dict(entry.data[CONF_USER_DATA])
    api_client = RoborockApiClient(entry.data[CONF_USERNAME], entry.data[CONF_BASE_URL])
    _LOGGER.debug("Getting home data")
    home_data = await api_client.get_home_data(user_data)
    _LOGGER.debug("Got home data %s", home_data)
    devices: list[HomeDataDevice] = home_data.devices + home_data.received_devices
    # Create a mqtt_client, which is needed to get the networking information of the device for local connection and in the future, get the map.
    mqtt_client = RoborockMqttClient(
        user_data, {device.duid: RoborockDeviceInfo(device) for device in devices}
    )
    network_results = await asyncio.gather(
        *(mqtt_client.get_networking(device.duid) for device in devices)
    )
    network_info = {
        device.duid: result
        for device, result in zip(devices, network_results)
        if result is not None
    }
    await mqtt_client.async_disconnect()
    if not network_info:
        raise ConfigEntryNotReady(
            "Could not get network information about your devices"
        )

    product_info = {product.id: product for product in home_data.products}
    coordinator = RoborockDataUpdateCoordinator(
        hass,
        devices,
        network_info,
        product_info,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id].release()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
