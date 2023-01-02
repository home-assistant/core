"""The 2N Telekomunikace integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from async_timeout import timeout
from py2n import Py2NConnectionData, Py2NDevice
from py2n.exceptions import ApiError, DeviceApiError, Py2NError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import aiohttp_client, device_registry
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.SWITCH]

SCAN_INTERNVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 2N Telekomunikace device from a config entry."""
    try:
        device = await Py2NDevice.create(
            aiohttp_client.async_get_clientsession(hass),
            options=Py2NConnectionData(
                host=entry.data[CONF_HOST],
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
            ),
        )
    except DeviceApiError as err:
        if (
            err.error is ApiError.AUTHORIZATION_REQUIRED
            or ApiError.INSUFFICIENT_PRIVILEGES
        ):
            entry.async_start_reauth(hass)
    except Py2NError as err:
        raise ConfigEntryNotReady from err

    coordinator = Py2NDeviceCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class Py2NDeviceCoordinator(DataUpdateCoordinator[Py2NDevice]):
    """Class to fetch data from 2N Telekomunikace devices."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, device: Py2NDevice) -> None:
        """Initialize."""
        self.device = device

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERNVAL)

    async def _async_update_data(self) -> Py2NDevice:
        """Update data via library."""
        async with timeout(10):
            try:
                await self.device.update()
            except DeviceApiError as err:
                if (
                    err.error is ApiError.AUTHORIZATION_REQUIRED
                    or ApiError.INSUFFICIENT_PRIVILEGES
                ):
                    self.config_entry.async_start_reauth(self.hass)
            except Py2NError as error:
                raise UpdateFailed(error) from error
            return self.device


class Py2NDeviceEntity(CoordinatorEntity[Py2NDeviceCoordinator]):
    """Helper class to represent a 2N Telekomunikace entity."""

    def __init__(
        self,
        coordinator: Py2NDeviceCoordinator,
        description: EntityDescription,
        device: Py2NDevice,
    ) -> None:
        """Initialize 2N Telekomunikace entity."""
        super().__init__(coordinator)
        self.device = device

        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://{device.data.host}/",
            connections={(device_registry.CONNECTION_NETWORK_MAC, device.data.mac)},
            manufacturer="2N Telekomunikace",
            model=device.data.model,
            name=device.data.name,
            sw_version=device.data.firmware,
            hw_version=device.data.hardware,
        )

        self._attr_unique_id = f"{device.data.mac}_{description.name}"
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.coordinator.async_add_listener(self._update_callback))

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()

    async def safe_request(self, action: Callable[[], Any]) -> None:
        """Safely run a library request."""

        try:
            await action()
        except DeviceApiError as err:
            if (
                err.error is ApiError.AUTHORIZATION_REQUIRED
                or ApiError.INSUFFICIENT_PRIVILEGES
            ):
                self.coordinator.config_entry.async_start_reauth(self.hass)
        except Py2NError as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                f"Request from library for entity {self.name} failed" f" {repr(err)}"
            ) from err
