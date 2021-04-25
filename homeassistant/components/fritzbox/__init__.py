"""Support for AVM Fritz!Box smarthome devices."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from pyfritzhome import Fritzhome, FritzhomeDevice, LoginError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_CONNECTIONS, CONF_COORDINATOR, DOMAIN, LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the AVM Fritz!Box platforms."""
    fritz = Fritzhome(
        host=entry.data[CONF_HOST],
        user=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await hass.async_add_executor_job(fritz.login)
    except LoginError as err:
        raise ConfigEntryAuthFailed from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CONNECTIONS: fritz,
    }

    def _update_fritz_devices() -> dict[str, FritzhomeDevice]:
        """Update all fritzbox device data."""
        try:
            devices = fritz.get_devices()
        except requests.exceptions.HTTPError:
            # If the device rebooted, login again
            try:
                fritz.login()
            except requests.exceptions.HTTPError as ex:
                raise ConfigEntryAuthFailed from ex
            devices = fritz.get_devices()

        data = {}
        for device in devices:
            device.update()
            data[device.ain] = device
        return data

    async def async_update_coordinator():
        """Fetch all device data."""
        return await hass.async_add_executor_job(_update_fritz_devices)

    hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ] = coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{entry.entry_id}",
        update_method=async_update_coordinator,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    def logout_fritzbox(event):
        """Close connections to this fritzbox."""
        fritz.logout()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, logout_fritzbox)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the AVM Fritz!Box platforms."""
    fritz = hass.data[DOMAIN][entry.entry_id][CONF_CONNECTIONS]
    await hass.async_add_executor_job(fritz.logout)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FritzBoxEntity(CoordinatorEntity):
    """Basis FritzBox entity."""

    def __init__(
        self,
        entity_info: dict[str, str],
        coordinator: DataUpdateCoordinator,
        ain: str,
    ):
        """Initialize the FritzBox entity."""
        super().__init__(coordinator)

        self.ain = ain
        self._name = entity_info[ATTR_NAME]
        self._unique_id = entity_info[ATTR_ENTITY_ID]
        self._unit_of_measurement = entity_info[ATTR_UNIT_OF_MEASUREMENT]
        self._device_class = entity_info[ATTR_DEVICE_CLASS]

    @property
    def device(self) -> FritzhomeDevice:
        """Return device object from coordinator."""
        return self.coordinator.data[self.ain]

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.device.name,
            "identifiers": {(DOMAIN, self.ain)},
            "manufacturer": self.device.manufacturer,
            "model": self.device.productname,
            "sw_version": self.device.fw_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class
