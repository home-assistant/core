"""Support for TaHoma water heater devices."""
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER

from .const import DOMAIN
from .water_heater_devices.domestic_hot_water_production import (
    DomesticHotWaterProduction,
)
from .water_heater_devices.hitachi_dhw import HitachiDHW

# TaHoma device widget to Device Entity class
SUPPORTED_DEVICES = {
    "DomesticHotWaterProduction": DomesticHotWaterProduction,
    "HitachiDHW": HitachiDHW,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma water heater from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        SUPPORTED_DEVICES[device.widget](device.deviceurl, coordinator)
        for device in data["platforms"][WATER_HEATER]
        if device.widget in SUPPORTED_DEVICES
    ]

    async_add_entities(entities)
