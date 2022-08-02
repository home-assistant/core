"""The MyQ integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import pymyq
from pymyq.const import (
    DEVICE_STATE as MYQ_DEVICE_STATE,
    DEVICE_STATE_ONLINE as MYQ_DEVICE_STATE_ONLINE,
    KNOWN_MODELS,
    MANUFACTURER,
)
from pymyq.device import MyQDevice
from pymyq.errors import InvalidCredentialsError, MyQError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY, PLATFORMS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyQ from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    websession = aiohttp_client.async_get_clientsession(hass)
    conf = entry.data

    try:
        myq = await pymyq.login(conf[CONF_USERNAME], conf[CONF_PASSWORD], websession)
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed from err
    except MyQError as err:
        raise ConfigEntryNotReady from err

    # Called by DataUpdateCoordinator, allows to capture any MyQError exceptions and to throw an HASS UpdateFailed
    # exception instead, preventing traceback in HASS logs.
    async def async_update_data():
        try:
            return await myq.update_device_info()
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except MyQError as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="myq devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    hass.data[DOMAIN][entry.entry_id] = {MYQ_GATEWAY: myq, MYQ_COORDINATOR: coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class MyQEntity(CoordinatorEntity):
    """Base class for MyQ Entities."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: MyQDevice) -> None:
        """Initialize class."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = device.device_id

    @property
    def name(self):
        """Return the name if any, name can change if user changes it within MyQ."""
        return self._device.name

    @property
    def device_info(self):
        """Return the device_info of the device."""
        model = (
            KNOWN_MODELS.get(self._device.device_id[2:4])
            if self._device.device_id is not None
            else None
        )
        via_device: tuple[str, str] | None = None
        if self._device.parent_device_id:
            via_device = (DOMAIN, self._device.parent_device_id)
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            manufacturer=MANUFACTURER,
            model=model,
            name=self._device.name,
            sw_version=self._device.firmware_version,
            via_device=via_device,
        )

    @property
    def available(self):
        """Return if the device is online."""
        # Not all devices report online so assume True if its missing
        return super().available and self._device.device_json[MYQ_DEVICE_STATE].get(
            MYQ_DEVICE_STATE_ONLINE, True
        )
