"""The Renson integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from renson_endura_delta.renson import Level, RensonVentilation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson from a config entry."""

    api = RensonVentilation(entry.data[CONF_HOST])
    coordinator = RensonCoordinator(hass, api)
    fw_coordinator = RensonFirmwareCoordinator(hass, api)

    if not await hass.async_add_executor_job(api.connect):
        raise ConfigEntryNotReady("Cannot connect to Renson device")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "fw_coordinator": fw_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hass.async_add_executor_job(setup_hass_services, hass, api)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup_hass_services(hass: HomeAssistant, renson_api: RensonVentilation) -> None:
    """Set up the Renson platforms."""

    async def set_timer_level(call: ServiceCall) -> None:
        """Set timer level."""
        level_string = call.data.get("timer_level", "Level1")
        time = call.data.get("time", 0)
        level = Level[level_string.upper()]

        await hass.async_add_executor_job(renson_api.set_timer_level, level, time)

    async def sync_time(call: ServiceCall) -> None:
        """Sync time of device."""
        await hass.async_add_executor_job(renson_api.sync_time)

    async def set_manual_level(call: ServiceCall) -> None:
        """Set manual level."""
        level_string = call.data.get("manual_level", "Off")
        level = Level[level_string.upper()]

        await hass.async_add_executor_job(renson_api.set_manual_level, level)

    async def set_breeze(call: ServiceCall) -> None:
        """Configure breeze feature."""
        level = call.data.get("breeze_level", "")
        temperature = call.data.get("temperature", 0)
        activated = call.data.get("activate", False)

        await hass.async_add_executor_job(
            renson_api.set_breeze, level, temperature, activated
        )

    async def set_day_night_time(call: ServiceCall) -> None:
        """Configure day night times."""
        day = call.data.get("day", "7:00")
        night = call.data.get("night", "22:00")

        await hass.async_add_executor_job(renson_api.set_time, day, night)

    async def set_pollution_settings(call: ServiceCall) -> None:
        """Configure pollutions settings."""
        day = call.data.get("day_pollution_level", "")
        night = call.data.get("night_pollution_level", "")
        humidity_control = call.data.get("humidity_control", "")
        airquality_control = call.data.get("airquality_control", "")
        co2_control = call.data.get("co2_control", "")
        co2_threshold = call.data.get("co2_threshold", 0)
        co2_hysteresis = call.data.get("co2_hysteresis", 0)

        await renson_api.set_pollution(
            day,
            night,
            humidity_control,
            airquality_control,
            co2_control,
            co2_threshold,
            co2_hysteresis,
        )

    async def set_filter_days(call: ServiceCall) -> None:
        """Set filter dayes."""
        days = call.data.get("days", 90)

        await hass.async_add_executor_job(renson_api.set_filter_days, days)

    hass.services.async_register(DOMAIN, "set_manual_level", set_manual_level)
    hass.services.async_register(DOMAIN, "set_breeze", set_breeze)
    hass.services.async_register(DOMAIN, "set_day_night_time", set_day_night_time)
    hass.services.async_register(
        DOMAIN, "set_pollution_settings", set_pollution_settings
    )
    hass.services.async_register(DOMAIN, "set_filter_days", set_filter_days)
    hass.services.async_register(DOMAIN, "set_timer_level", set_timer_level)
    hass.services.async_register(DOMAIN, "sync_time", sync_time)


class RensonCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Renson."""

    def __init__(self, hass, api, update_interval=timedelta(seconds=30)):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Renson",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                return await self.hass.async_add_executor_job(self.api.get_all_data)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class RensonFirmwareCoordinator(RensonCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            api,
            update_interval=timedelta(seconds=60 * 60 * 24),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        data = await super()._async_update_data()

        try:
            async with async_timeout.timeout(30):
                latest_version = await self.hass.async_add_executor_job(
                    self.api.get_latest_firmware_version
                )
                data["latest_firmware_version"] = latest_version
                return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
