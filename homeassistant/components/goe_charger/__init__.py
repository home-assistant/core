"""The go-e Charger integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry

from .const import DOMAIN
from .common import GoeChargerHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["binary_sensor", "number", "select", "sensor"]


async def async_setup(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the go-eCharger integration."""

    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up go-e Charger from a config entry."""

    async def async_update_data():
        """Fetch data from API endpoint."""
        hub = GoeChargerHub(config_entry.data["secure"], config_entry.data["host"], config_entry.data["pathprefix"])

        try:
            keys = [
                "alw", "acu", "adi", "sse", "eto", "ccw", "rssi", "lmo", "amp", "fna", "car", "err", "cbl", "wh", "fwv",
                "oem", "typ",
                "tma", "nrg", "modelStatus", "var", "fhz", "ust", "acs", "frc", "psm", "loc"
            ]
            data = await hub.get_data(hass, keys)

            dr = await device_registry.async_get_registry(hass)
            dr.async_get_or_create(
                name=data["fna"],
                config_entry_id=config_entry.entry_id,
                # connections={(device_registry.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66")},
                identifiers={(DOMAIN, config_entry.data["serial"])},
                manufacturer=data["oem"],
                model=data["typ"] + " (" + str(data["var"]) + "kW)",
                # suggested_area="Kitchen",
                sw_version=data["fwv"],
            )

            return data
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception %s", str(e))
            return None

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="goe_charger_" + config_entry.data["serial"],
        update_method=async_update_data,
        update_interval=timedelta(seconds=5),
    )

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    if coordinator.data is None:
        dr = await device_registry.async_get_registry(hass)
        dr.async_get_or_create(
            name="go-e_Charger_" + config_entry.data["serial"],
            config_entry_id=config_entry.entry_id,
            # connections={(device_registry.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66")},
            identifiers={(DOMAIN, config_entry.data["serial"])},
            manufacturer="<unknown>",
            model="<unknown>",
            # suggested_area="Kitchen",
            sw_version="<unknown>",
        )

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        logging.warning('unload platforms failed')
        return False;

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True
