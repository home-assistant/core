"""Coordinator for the Moehlenhoff Alpha2."""

import asyncio
from collections import defaultdict
from datetime import timedelta
import logging
from typing import override

import aiohttp
from moehlenhoff_alpha2 import Alpha2Base

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)

type Alpha2ConfigEntry = ConfigEntry[Alpha2BaseCoordinator]


class Alpha2BaseCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Keep the base instance in one place and centralize the update."""

    config_entry: Alpha2ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: Alpha2ConfigEntry, base: Alpha2Base
    ) -> None:
        """Initialize Alpha2Base data updater."""
        self.base = base
        self._heat_area_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="alpha2_base",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, dict[str, dict]]:
        """Fetch the latest data from the source."""
        heat_areas_before_update = (
            {
                heat_area_id: heat_area.copy()
                for heat_area_id, heat_area in self.data["heat_areas"].items()
            }
            if self.data is not None
            else {}
        )
        await self.base.update_data()
        data = {
            "heat_areas": {ha["ID"]: ha for ha in self.base.heat_areas if ha.get("ID")},
            "heat_controls": {
                hc["ID"]: hc for hc in self.base.heat_controls if hc.get("ID")
            },
            "io_devices": {io["ID"]: io for io in self.base.io_devices if io.get("ID")},
        }
        if self.data is not None:
            for heat_area_id, heat_area in self.data["heat_areas"].items():
                if (updated_heat_area := data["heat_areas"].get(heat_area_id)) is None:
                    continue
                previous_heat_area = heat_areas_before_update.get(heat_area_id, {})
                for attribute, value in heat_area.items():
                    if (
                        attribute not in previous_heat_area
                        or previous_heat_area[attribute] != value
                    ):
                        updated_heat_area[attribute] = value

        return data

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

        update_data: dict[str, float | int] = {"T_TARGET": target_temperature}
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

        await self.async_set_heat_area_attributes(heat_area_id, update_data)

    async def async_set_heat_area_attributes(
        self, heat_area_id: str, attributes: dict[str, float | int]
    ) -> None:
        """Set attributes of the given heat area."""
        async with self._heat_area_locks[heat_area_id]:
            heat_area = self.data["heat_areas"][heat_area_id]
            minimum = attributes.get("T_TARGET_MIN", heat_area.get("T_TARGET_MIN", 0))
            maximum = attributes.get("T_TARGET_MAX", heat_area.get("T_TARGET_MAX", 50))
            if minimum > maximum:
                raise HomeAssistantError(
                    "The minimum target temperature must not exceed the maximum"
                )

            try:
                await self.base.update_heat_area(heat_area_id, attributes)
            except (aiohttp.ClientError, TimeoutError) as http_err:
                raise HomeAssistantError(
                    "Failed to set heat area settings, communication error with alpha2 base"
                ) from http_err

            self.data["heat_areas"][heat_area_id].update(attributes)
            self.async_update_listeners()

    async def async_set_heat_area_mode(
        self, heat_area_id: str, heat_area_mode: int
    ) -> None:
        """Set the mode of the given heat area."""
        # HEATAREA_MODE: 0=Auto, 1=Tag, 2=Nacht
        if heat_area_mode not in (0, 1, 2):
            raise ValueError(f"Invalid heat area mode: {heat_area_mode}")
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
