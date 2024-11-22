"""The Roborock component."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from roborock import HomeDataRoom, RoborockException, RoborockInvalidCredentials
from roborock.containers import DeviceData, HomeDataDevice, HomeDataProduct, UserData
from roborock.version_1_apis.roborock_mqtt_client_v1 import RoborockMqttClientV1
from roborock.version_a01_apis import RoborockMqttClientA01
from roborock.web_api import RoborockApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_BASE_URL, CONF_USER_DATA, DOMAIN, PLATFORMS
from .coordinator import RoborockDataUpdateCoordinator, RoborockDataUpdateCoordinatorA01

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

type RoborockConfigEntry = ConfigEntry[RoborockCoordinators]


@dataclass
class RoborockCoordinators:
    """Roborock coordinators type."""

    v1: list[RoborockDataUpdateCoordinator]
    a01: list[RoborockDataUpdateCoordinatorA01]

    def values(
        self,
    ) -> list[RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01]:
        """Return all coordinators."""
        return self.v1 + self.a01


async def async_setup_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Set up roborock from a config entry."""

    entry.async_on_unload(entry.add_update_listener(update_listener))

    user_data = UserData.from_dict(entry.data[CONF_USER_DATA])
    api_client = RoborockApiClient(entry.data[CONF_USERNAME], entry.data[CONF_BASE_URL])
    _LOGGER.debug("Getting home data")
    try:
        home_data = await api_client.get_home_data_v2(user_data)
    except RoborockInvalidCredentials as err:
        raise ConfigEntryAuthFailed(
            "Invalid credentials",
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except RoborockException as err:
        raise ConfigEntryNotReady(
            "Failed to get Roborock home data",
            translation_domain=DOMAIN,
            translation_key="home_data_fail",
        ) from err
    _LOGGER.debug("Got home data %s", home_data)
    all_devices: list[HomeDataDevice] = home_data.devices + home_data.received_devices
    device_map: dict[str, HomeDataDevice] = {
        device.duid: device for device in all_devices
    }
    product_info: dict[str, HomeDataProduct] = {
        product.id: product for product in home_data.products
    }
    # Get a Coordinator if the device is available or if we have connected to the device before
    coordinators = await asyncio.gather(
        *build_setup_functions(
            hass, device_map, user_data, product_info, home_data.rooms
        ),
        return_exceptions=True,
    )
    # Valid coordinators are those where we had networking cached or we could get networking
    v1_coords = [
        coord
        for coord in coordinators
        if isinstance(coord, RoborockDataUpdateCoordinator)
    ]
    a01_coords = [
        coord
        for coord in coordinators
        if isinstance(coord, RoborockDataUpdateCoordinatorA01)
    ]
    if len(v1_coords) + len(a01_coords) == 0:
        raise ConfigEntryNotReady(
            "No devices were able to successfully setup",
            translation_domain=DOMAIN,
            translation_key="no_coordinators",
        )
    valid_coordinators = RoborockCoordinators(v1_coords, a01_coords)

    async def on_unload() -> None:
        release_tasks = set()
        for coordinator in valid_coordinators.values():
            release_tasks.add(coordinator.release())
        await asyncio.gather(*release_tasks)

    entry.async_on_unload(on_unload)
    entry.runtime_data = valid_coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def build_setup_functions(
    hass: HomeAssistant,
    device_map: dict[str, HomeDataDevice],
    user_data: UserData,
    product_info: dict[str, HomeDataProduct],
    home_data_rooms: list[HomeDataRoom],
) -> list[
    Coroutine[
        Any,
        Any,
        RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01 | None,
    ]
]:
    """Create a list of setup functions that can later be called asynchronously."""
    return [
        setup_device(
            hass, user_data, device, product_info[device.product_id], home_data_rooms
        )
        for device in device_map.values()
    ]


async def setup_device(
    hass: HomeAssistant,
    user_data: UserData,
    device: HomeDataDevice,
    product_info: HomeDataProduct,
    home_data_rooms: list[HomeDataRoom],
) -> RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01 | None:
    """Set up a coordinator for a given device."""
    if device.pv == "1.0":
        return await setup_device_v1(
            hass, user_data, device, product_info, home_data_rooms
        )
    if device.pv == "A01":
        return await setup_device_a01(hass, user_data, device, product_info)
    _LOGGER.warning(
        "Not adding device %s because its protocol version %s or category %s is not supported",
        device.duid,
        device.pv,
        product_info.category.name,
    )
    return None


async def setup_device_v1(
    hass: HomeAssistant,
    user_data: UserData,
    device: HomeDataDevice,
    product_info: HomeDataProduct,
    home_data_rooms: list[HomeDataRoom],
) -> RoborockDataUpdateCoordinator | None:
    """Set up a device Coordinator."""
    mqtt_client = await hass.async_add_executor_job(
        RoborockMqttClientV1, user_data, DeviceData(device, product_info.model)
    )
    try:
        networking = await mqtt_client.get_networking()
        if networking is None:
            # If the api does not return an error but does return None for
            # get_networking - then we need to go through cache checking.
            raise RoborockException("Networking request returned None.")  # noqa: TRY301
    except RoborockException as err:
        _LOGGER.warning(
            "Not setting up %s because we could not get the network information of the device. "
            "Please confirm it is online and the Roborock servers can communicate with it",
            device.name,
        )
        _LOGGER.debug(err)
        await mqtt_client.async_release()
        raise
    coordinator = RoborockDataUpdateCoordinator(
        hass, device, networking, product_info, mqtt_client, home_data_rooms
    )
    # Verify we can communicate locally - if we can't, switch to cloud api
    await coordinator.verify_api()
    coordinator.api.is_available = True
    try:
        await coordinator.get_maps()
    except RoborockException as err:
        _LOGGER.warning("Failed to get map data")
        _LOGGER.debug(err)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as ex:
        await coordinator.release()
        if isinstance(coordinator.api, RoborockMqttClientV1):
            _LOGGER.warning(
                "Not setting up %s because the we failed to get data for the first time using the online client. "
                "Please ensure your Home Assistant instance can communicate with this device. "
                "You may need to open firewall instances on your Home Assistant network and on your Vacuum's network",
                device.name,
            )
            # Most of the time if we fail to connect using the mqtt client, the problem is due to firewall,
            # but in case if it isn't, the error can be included in debug logs for the user to grab.
            if coordinator.last_exception:
                _LOGGER.debug(coordinator.last_exception)
                raise coordinator.last_exception from ex
        elif coordinator.last_exception:
            # If this is reached, we have verified that we can communicate with the Vacuum locally,
            # so if there is an error here - it is not a communication issue but some other problem
            extra_error = f"Please create an issue with the following error included: {coordinator.last_exception}"
            _LOGGER.warning(
                "Not setting up %s because the coordinator failed to get data for the first time using the "
                "offline client %s",
                device.name,
                extra_error,
            )
            raise coordinator.last_exception from ex
    return coordinator


async def setup_device_a01(
    hass: HomeAssistant,
    user_data: UserData,
    device: HomeDataDevice,
    product_info: HomeDataProduct,
) -> RoborockDataUpdateCoordinatorA01 | None:
    """Set up a A01 protocol device."""
    mqtt_client = RoborockMqttClientA01(
        user_data, DeviceData(device, product_info.name), product_info.category
    )
    coord = RoborockDataUpdateCoordinatorA01(hass, device, product_info, mqtt_client)
    await coord.async_config_entry_first_refresh()
    return coord


async def async_unload_entry(hass: HomeAssistant, entry: RoborockConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: RoborockConfigEntry) -> None:
    """Handle options update."""
    # Reload entry to update data
    await hass.config_entries.async_reload(entry.entry_id)
