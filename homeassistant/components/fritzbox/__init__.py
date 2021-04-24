"""Support for AVM Fritz!Box smarthome devices."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import socket

from pyfritzhome import Fritzhome, FritzhomeDevice, LoginError
import requests
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_CONNECTIONS,
    CONF_COORDINATOR,
    CONF_RETRY,
    DEFAULT_HOST,
    DEFAULT_USERNAME,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)


def ensure_unique_hosts(value):
    """Validate that all configs have a unique host."""
    vol.Schema(vol.Unique("duplicate host entries found"))(
        [socket.gethostbyname(entry[CONF_HOST]) for entry in value]
    )
    return value


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_DEVICES): vol.All(
                        cv.ensure_list,
                        [
                            vol.Schema(
                                {
                                    vol.Required(
                                        CONF_HOST, default=DEFAULT_HOST
                                    ): cv.string,
                                    vol.Required(CONF_PASSWORD): cv.string,
                                    vol.Required(
                                        CONF_USERNAME, default=DEFAULT_USERNAME
                                    ): cv.string,
                                }
                            )
                        ],
                        ensure_unique_hosts,
                    )
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, str]) -> bool:
    """Set up the AVM Fritz!Box integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN][CONF_DEVICES]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
                )
            )

    return True


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
        CONF_RETRY: False,
    }

    async def async_update_coordinator():
        """Fetch all device data."""
        try:
            devices = await hass.async_add_executor_job(fritz.get_devices)
        except requests.exceptions.HTTPError as ex:
            if hass.data[DOMAIN][entry.entry_id][CONF_RETRY]:
                raise ConfigEntryAuthFailed from ex
            else:
                hass.data[DOMAIN][entry.entry_id][CONF_RETRY] = True
                raise UpdateFailed(f"Fritzhome connection error: {ex}") from ex

        data = {}
        for device in devices:
            await hass.async_add_executor_job(device.update)
            data[device.ain] = device
        return data

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
