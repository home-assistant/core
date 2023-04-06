"""The Roborock component."""
from __future__ import annotations

from datetime import timedelta
import logging

from roborock.api import RoborockApiClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import (
    HomeDataDevice,
    HomeDataProduct,
    RoborockDeviceInfo,
    UserData,
)
from roborock.local_api import RoborockLocalClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_URL, CONF_USER_DATA, DOMAIN, PLATFORMS
from .coordinator import RoborockDataUpdateCoordinator
from .models import RoborockHassDeviceInfo

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

    devices_info: dict[str, RoborockDeviceInfo] = {}
    devices: list[HomeDataDevice] = home_data.devices + home_data.received_devices
    for device in devices:
        devices_info[device.duid] = RoborockDeviceInfo(device)
    # Create a mqtt_client, which is needed to get the networking information of the device for local connection and in the future, get the map.
    mqtt_client = RoborockMqttClient(user_data, devices_info)
    for device in devices:
        networking = await mqtt_client.get_networking(device.duid)
        if networking is None:
            _LOGGER.warning("Device %s is offline and cannot be setup", device.duid)
            devices_info.pop(device.duid)
            continue
        product: HomeDataProduct = next(
            (
                product
                for product in home_data.products
                if product.id == device.product_id
            ),
            {},
        )

        devices_info[device.duid] = RoborockHassDeviceInfo(device, networking, product)
    await mqtt_client.async_disconnect()
    client = RoborockLocalClient(devices_info)
    coordinator = RoborockDataUpdateCoordinator(hass, client, devices_info)

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
