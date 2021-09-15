"""The Renson Endura Delta integration."""
from __future__ import annotations

import rensonVentilationLib.generalEnum as rensonEnums
import rensonVentilationLib.renson as renson

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson Endura Delta from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = renson.RensonVentilation(entry.data["host"])

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Handle all the services of the Renson API."""

    def handle_manual_level_set(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        level = call.data.get("manual_level", "Off").upper()
        service.set_manual_level(rensonEnums.ManualLevel[level])

    def handle_sync_time(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        service.sync_time()

    def handle_timer_level(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        level = rensonEnums.TimerLevel[call.data.get("timer_level", "Level1").upper()]
        time = call.data.get("time", 0)

        service.set_timer_level(level, time)

    def handle_set_breeze(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        level = rensonEnums.ManualLevel[call.data.get("breeze_level", "Off").upper()]
        temperature = call.data.get("temperature", 0)
        activated = call.data.get("activate", False)

        service.set_breeze(level, temperature, activated)

    def handle_set_time(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        day = call.data.get("day", "7:00")
        night = call.data.get("night", "22:00")

        service.set_time(day, night)

    def handle_set_pollution(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        day = call.data.get("day_pollution_level", "")
        night = call.data.get("night_pollution_level", "")
        humidity_control = call.data.get("humidity_control", "")
        airquality_control = call.data.get("airquality_control", "")
        co2_control = call.data.get("co2_control", "")
        co2_threshold = call.data.get("co2_threshold", 0)
        co2_hysteresis = call.data.get("co2_hysteresis", 0)

        service.set_pollution(
            day,
            night,
            humidity_control,
            airquality_control,
            co2_control,
            co2_threshold,
            co2_hysteresis,
        )

    def set_filter_days(call: ServiceCall):
        service: renson.RensonVentilation = renson.RensonVentilation(
            hass.config_entries.async_entries(DOMAIN)[0].data["host"]
        )
        days = call.data.get("days", 90)

        service.set_filter_days(days)

    hass.services.register(DOMAIN, "manual_level", handle_manual_level_set)
    hass.services.register(DOMAIN, "sync_time", handle_sync_time)
    hass.services.register(DOMAIN, "timer_level", handle_timer_level)
    hass.services.register(DOMAIN, "set_breeze", handle_set_breeze)
    hass.services.register(DOMAIN, "set_day_night_time", handle_set_time)
    hass.services.register(DOMAIN, "set_pollution_settings", handle_set_pollution)
    hass.services.register(DOMAIN, "set_filter_days", set_filter_days)

    return True
