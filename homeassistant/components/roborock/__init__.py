"""The Roborock component."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from roborock.api import RoborockApiClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import DeviceData, HomeDataDevice, UserData
from roborock.exceptions import RoborockException

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
    try:
        home_data = await api_client.get_home_data(user_data)
    except RoborockException as err:
        raise ConfigEntryNotReady("Failed getting Roborock home_data.") from err
    _LOGGER.debug("Got home data %s", home_data)
    device_map: dict[str, HomeDataDevice] = {
        device.duid: device for device in home_data.devices + home_data.received_devices
    }
    product_info = {product.id: product for product in home_data.products}
    # Create a mqtt_client, which is needed to get the networking information of the device for local connection and in the future, get the map.
    mqtt_clients = {
        device.duid: RoborockMqttClient(
            user_data, DeviceData(device, product_info[device.product_id].model)
        )
        for device in device_map.values()
    }
    network_results = await asyncio.gather(
        *(mqtt_client.get_networking() for mqtt_client in mqtt_clients.values()),
        return_exceptions=True,
    )
    network_info = {}
    for device, result in zip(device_map.values(), network_results):
        if result is None:
            _LOGGER.warning(
                "Failed to connect to get networking information about %s because the result was None",
                device.duid,
            )
        elif isinstance(result, RoborockException):
            _LOGGER.warning(
                "Failed to connect to get networking information about %s", device.duid
            )
            _LOGGER.exception(result)
        else:
            network_info[device.duid] = result
    if not network_info:
        raise ConfigEntryNotReady(
            "Could not get network information about your devices"
        )
    coordinator_map: dict[str, RoborockDataUpdateCoordinator] = {}
    for device_id, device in device_map.items():
        if device_id not in network_info:
            continue
        coordinator_map[device_id] = RoborockDataUpdateCoordinator(
            hass,
            device,
            network_info[device_id],
            product_info[device.product_id],
            mqtt_clients[device.duid],
        )
    await asyncio.gather(
        *(coordinator.verify_api() for coordinator in coordinator_map.values())
    )
    # If one device update fails - we still want to set up other devices
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinator_map.values()
        ),
        return_exceptions=True,
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        device_id: coordinator
        for device_id, coordinator in coordinator_map.items()
        if coordinator.last_update_success
    }  # Only add coordinators that succeeded

    if not hass.data[DOMAIN][entry.entry_id]:
        # Don't start if no coordinators succeeded.
        raise ConfigEntryNotReady("There are no devices that can currently be reached.")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await asyncio.gather(
            *(
                coordinator.release()
                for coordinator in hass.data[DOMAIN][entry.entry_id].values()
            )
        )
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
