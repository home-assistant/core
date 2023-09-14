"""The Roborock component."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
import logging

from roborock.api import RoborockApiClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import (
    DeviceData,
    HomeDataDevice,
    HomeDataProduct,
    NetworkInfo,
    UserData,
)
from roborock.exceptions import RoborockException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BASE_URL,
    CONF_CACHED_INFORMATION,
    CONF_USER_DATA,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import RoborockDataUpdateCoordinator
from .models import CachedCoordinatorInformation

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
    # Get a Coordinator if the device is available or if we have connected to the device before
    coordinators = await asyncio.gather(
        *(
            setup_device(
                hass,
                user_data,
                device,
                product_info[device.product_id],
                CachedCoordinatorInformation(
                    network_info=NetworkInfo(
                        **entry.data[CONF_CACHED_INFORMATION][device.duid][
                            "network_info"
                        ]
                    ),
                    supported_entities=set(
                        entry.data[CONF_CACHED_INFORMATION][device.duid][
                            "supported_entities"
                        ]
                    ),
                )
                if device.duid in entry.data[CONF_CACHED_INFORMATION]
                else None,
            )
            for device in device_map.values()
        )
    )
    valid_coordinators: list[RoborockDataUpdateCoordinator] = [
        coord for coord in coordinators if coord is not None
    ]
    if len(valid_coordinators) == 0:
        raise ConfigEntryNotReady("No coordinators were able to successfully setup.")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        coordinator.roborock_device_info.device.duid: coordinator
        for coordinator in valid_coordinators
        if coordinator.last_update_success
    }  # Only add coordinators that succeeded

    if not hass.data[DOMAIN][entry.entry_id]:
        # Don't start if no coordinators succeeded.
        raise ConfigEntryNotReady("There are no devices that can currently be reached.")
    updated_cached: dict[str, dict] = {}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for coord in valid_coordinators:
        updated_cached.update(
            {
                coord.roborock_device_info.device.duid: asdict(
                    CachedCoordinatorInformation(
                        network_info=coord.roborock_device_info.network_info,
                        supported_entities=coord.supported_entities,
                    )
                )
            }
        )
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CACHED_INFORMATION: updated_cached}
    )
    return True


async def setup_device(
    hass: HomeAssistant,
    user_data: UserData,
    device: HomeDataDevice,
    product_info: HomeDataProduct,
    cached_data: CachedCoordinatorInformation | None,
) -> RoborockDataUpdateCoordinator | None:
    """Set up a device Coordinator."""
    mqtt_client = RoborockMqttClient(user_data, DeviceData(device, product_info.name))
    try:
        networking = await mqtt_client.get_networking()
    except RoborockException as err:
        if cached_data is None:
            # If we have never added this device before - don't start now.
            _LOGGER.warning(
                "Not setting up %s because we could not get the network information of the device. "
                "Please confirm it is online and the Roborock servers can communicate with it",
                device.name,
            )
            _LOGGER.debug(err)
            return None
        # If cached data exist, then we have set up this vacuum before, and we have cached network information.
        networking = cached_data.network_info
    coordinator = RoborockDataUpdateCoordinator(
        hass, device, networking, product_info, mqtt_client
    )
    coordinator.supported_entities = (
        cached_data.supported_entities if cached_data is not None else set()
    )
    # Verify we can communicate locally - if we can't, switch to cloud api
    await coordinator.verify_api()
    coordinator.api.is_available = True
    exception = None
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as ex:
        exception = ex.__cause__
    if not coordinator.last_update_success:
        if isinstance(coordinator.api, RoborockMqttClient):
            _LOGGER.warning(
                "Not setting up %s because the we failed to get data for the first time using the online client. "
                "Please ensure your Home Assistant instance can communicate with this device. "
                "You may need to open firewall instances on your Home Assistant network and on your Vacuum's network",
                device.name,
            )
            # Most of the time if we fail to connect using the mqtt client, the problem is due to firewall,
            # but in case if it isn't, the error can be included in debug logs for the user to grab.
            if exception:
                _LOGGER.debug(exception)
        else:
            # If this is reached, we have verified that we can communicate with the Vacuum locally,
            # so if there is an error here - it is not a communication issue but some other problem
            extra_error = (
                f"Please create an issue with the following error included: {exception}"
                if exception is not None
                else "Setting up of the coordinator failed, but no exceptions were thrown."
            )
            _LOGGER.warning(
                "Not setting up %s because the coordinator failed to get data for the first time using the offline client %s",
                device.name,
                extra_error,
            )
        coordinator.api.is_available = False
    return coordinator


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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data, CONF_CACHED_INFORMATION: {}}
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
