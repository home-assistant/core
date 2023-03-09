"""The Roborock component."""
from __future__ import annotations

from datetime import timedelta
import logging

from roborock.api import RoborockClient, RoborockMqttClient
from roborock.containers import HomeDataProduct, UserData
from roborock.exceptions import RoborockException, RoborockTimeout
from roborock.typing import RoborockDeviceInfo, RoborockDeviceProp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BASE_URL,
    CONF_INCLUDE_SHARED,
    CONF_USER_DATA,
    DOMAIN,
    PLATFORMS,
    SERVICES,
    VACUUM,
)

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())

    user_data = UserData(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_USERNAME)
    vacuum_options = entry.options.get(VACUUM)
    include_shared = (
        vacuum_options.get(CONF_INCLUDE_SHARED) if vacuum_options else False
    )
    api_client = RoborockClient(username, base_url)
    _LOGGER.debug("Getting home data")
    home_data = await api_client.get_home_data(user_data)
    _LOGGER.debug("Got home data %s", home_data)

    device_map: dict[str, RoborockDeviceInfo] = {}
    devices = (
        home_data.devices + home_data.received_devices
        if include_shared
        else home_data.devices
    )
    for device in devices:
        product: HomeDataProduct = next(
            (
                HomeDataProduct(product)
                for product in home_data.products
                if product.id == device.product_id
            ),
            {},
        )
        device_map[device.duid] = RoborockDeviceInfo(device, product)

    client = RoborockMqttClient(user_data, device_map)
    coordinator = RoborockDataUpdateCoordinator(hass, client)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


class RoborockDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RoborockDeviceProp]]
):
    """Class to manage fetching data from the API."""

    ACCEPTABLE_NUMBER_OF_TIMEOUTS = 3

    def __init__(self, hass: HomeAssistant, client: RoborockMqttClient) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.platforms: list[str] = []
        self._devices_prop: dict[str, RoborockDeviceProp] = {}
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_disconnect()

    async def _get_device_prop(self, device_id: str) -> None:
        """Get device properties."""
        device_prop = await self.api.get_prop(device_id)
        if device_prop:
            if device_id in self._devices_prop:
                self._devices_prop[device_id].update(device_prop)
            else:
                self._devices_prop[device_id] = device_prop

    async def _async_update_data(self) -> dict[str, RoborockDeviceProp]:
        """Update data via library."""
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)
        try:
            for device_id, _ in self.api.device_map.items():
                await self._get_device_prop(device_id)
        except RoborockTimeout as ex:
            if self._devices_prop and self._timeout_countdown > 0:
                _LOGGER.debug(
                    "Timeout updating coordinator. Acceptable timeouts countdown = %s",
                    self._timeout_countdown,
                )
                self._timeout_countdown -= 1
            else:
                raise UpdateFailed(ex) from ex
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
        if self._devices_prop:
            return self._devices_prop
        raise UpdateFailed("No device props found")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id].release()
        hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data[DOMAIN]:
        for service in SERVICES:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
