"""Support for the Moehlenhoff Alpha2."""
from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from moehlenhoff_alpha2 import Alpha2Base

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR]

UPDATE_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    base = Alpha2Base(entry.data["host"])
    coordinator = Alpha2BaseCoordinator(hass, base)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class Alpha2BaseCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Keep the base instance in one place and centralize the update."""

    def __init__(self, hass: HomeAssistant, base: Alpha2Base) -> None:
        """Initialize Alpha2Base data updater."""
        self.base = base
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="alpha2_base",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, dict[str, dict]]:
        """Fetch the latest data from the source."""
        await self.base.update_data()
        return {
            "heat_areas": {ha["ID"]: ha for ha in self.base.heat_areas if ha.get("ID")},
            "heat_controls": {
                hc["ID"]: hc for hc in self.base.heat_controls if hc.get("ID")
            },
            "io_devices": {io["ID"]: io for io in self.base.io_devices if io.get("ID")},
        }

    def get_cooling(self) -> bool:
        """Return if cooling mode is enabled."""
        return self.base.cooling

    async def async_set_cooling(self, enabled: bool) -> None:
        """Enable or disable cooling mode."""
        await self.base.set_cooling(enabled)
        self.async_update_listeners()

    async def async_set_target_temperature(
        self, heat_area_id: str, target_temperature: float
    ) -> None:
        """Set the target temperature of the given heat area."""
        _LOGGER.debug(
            "Setting target temperature of heat area %s to %0.1f",
            heat_area_id,
            target_temperature,
        )

        update_data = {"T_TARGET": target_temperature}
        is_cooling = self.get_cooling()
        heat_area_mode = self.data["heat_areas"][heat_area_id]["HEATAREA_MODE"]
        if heat_area_mode == 1:
            if is_cooling:
                update_data["T_COOL_DAY"] = target_temperature
            else:
                update_data["T_HEAT_DAY"] = target_temperature
        elif heat_area_mode == 2:
            if is_cooling:
                update_data["T_COOL_NIGHT"] = target_temperature
            else:
                update_data["T_HEAT_NIGHT"] = target_temperature

        try:
            await self.base.update_heat_area(heat_area_id, update_data)
        except aiohttp.ClientError as http_err:
            raise HomeAssistantError(
                "Failed to set target temperature, communication error with alpha2 base"
            ) from http_err
        self.data["heat_areas"][heat_area_id].update(update_data)
        self.async_update_listeners()

    async def async_set_heat_area_mode(
        self, heat_area_id: str, heat_area_mode: int
    ) -> None:
        """Set the mode of the given heat area."""
        # HEATAREA_MODE: 0=Auto, 1=Tag, 2=Nacht
        if heat_area_mode not in (0, 1, 2):
            ValueError(f"Invalid heat area mode: {heat_area_mode}")
        _LOGGER.debug(
            "Setting mode of heat area %s to %d",
            heat_area_id,
            heat_area_mode,
        )
        try:
            await self.base.update_heat_area(
                heat_area_id, {"HEATAREA_MODE": heat_area_mode}
            )
        except aiohttp.ClientError as http_err:
            raise HomeAssistantError(
                "Failed to set heat area mode, communication error with alpha2 base"
            ) from http_err

        self.data["heat_areas"][heat_area_id]["HEATAREA_MODE"] = heat_area_mode
        is_cooling = self.get_cooling()
        if heat_area_mode == 1:
            if is_cooling:
                self.data["heat_areas"][heat_area_id]["T_TARGET"] = self.data[
                    "heat_areas"
                ][heat_area_id]["T_COOL_DAY"]
            else:
                self.data["heat_areas"][heat_area_id]["T_TARGET"] = self.data[
                    "heat_areas"
                ][heat_area_id]["T_HEAT_DAY"]
        elif heat_area_mode == 2:
            if is_cooling:
                self.data["heat_areas"][heat_area_id]["T_TARGET"] = self.data[
                    "heat_areas"
                ][heat_area_id]["T_COOL_NIGHT"]
            else:
                self.data["heat_areas"][heat_area_id]["T_TARGET"] = self.data[
                    "heat_areas"
                ][heat_area_id]["T_HEAT_NIGHT"]

        self.async_update_listeners()
