"""The Smartfox integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from smartfox import Smartfox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BATTERY_ENABLED,
    CONF_CAR_CHARGER_ENABLED,
    CONF_HEAT_PUMP_ENABLED,
    CONF_HOST,
    CONF_INTEVAL,
    CONF_NAME,
    CONF_PORT,
    CONF_SCHEME,
    CONF_VERIFY,
    CONF_WATER_SENSORS_ENABLED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]  # , Platform.SELECT, Platform.NUMBER


class SmartfoxCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        smartfox: Smartfox,
        device_info: DeviceInfo,
        update_interval: timedelta,
        name: str,
        car_charger_enabled: bool = False,
        heat_pump_enabled: bool = False,
        water_sensors_enabled: bool = False,
        battery_enabled: bool = False,
    ) -> None:
        """Initialize Smartfox Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Smartfox Data Coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=update_interval,
        )

        self.name = name
        self.smartfox = smartfox
        self.device_info = device_info

        self.car_charger_enabled = car_charger_enabled
        self.heat_pump_enabled = heat_pump_enabled
        self.water_sensors_enabled = water_sensors_enabled
        self.battery_enabled = battery_enabled

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(10):
                return await self.hass.async_add_executor_job(self.smartfox.getValues)
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Smartfox Coordinator update Exception: %s", exception)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smartfox from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    smartfox = Smartfox(
        scheme=entry.data[CONF_SCHEME],
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        verify=entry.data[CONF_VERIFY],
    )

    smartfox_device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_NAME])},
        name=entry.data[CONF_NAME],
        model="Smartfox",
        configuration_url=f"{entry.data[CONF_SCHEME]}://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/",
        via_device=(DOMAIN, entry.data[CONF_NAME]),
    )

    coordinator = SmartfoxCoordinator(
        hass=hass,
        smartfox=smartfox,
        device_info=smartfox_device_info,
        update_interval=timedelta(seconds=entry.data[CONF_INTEVAL]),
        name=entry.data[CONF_NAME],
        car_charger_enabled=entry.data[CONF_CAR_CHARGER_ENABLED],
        heat_pump_enabled=entry.data[CONF_HEAT_PUMP_ENABLED],
        water_sensors_enabled=entry.data[CONF_WATER_SENSORS_ENABLED],
        battery_enabled=entry.data[CONF_BATTERY_ENABLED],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
