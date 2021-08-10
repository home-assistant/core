"""Support for Adax wifi-enabled home heaters."""
from __future__ import annotations

import logging
from typing import Any

from adax import Adax

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACCOUNT_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Adax thermostat with config flow."""
    adax_data_handler = Adax(
        entry.data[ACCOUNT_ID],
        entry.data[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
    )

    async_add_entities(
        AdaxDevice(room, adax_data_handler)
        for room in await adax_data_handler.get_rooms()
    )


class AdaxDevice(ClimateEntity):
    """Representation of a heater."""

    def __init__(self, heater_data: dict[str, Any], adax_data_handler: Adax) -> None:
        """Initialize the heater."""
        self._heater_data = heater_data
        self._adax_data_handler = adax_data_handler

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._heater_data['homeId']}_{self._heater_data['id']}"

    @property
    def name(self) -> str:
        """Return the name of the device, if any."""
        return self._heater_data["name"]

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if self._heater_data["heatingEnabled"]:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def icon(self) -> str:
        """Return nice icon for heater."""
        if self.hvac_mode == HVAC_MODE_HEAT:
            return "mdi:radiator"
        return "mdi:radiator-off"

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            temperature = max(
                self.min_temp, self._heater_data.get("targetTemperature", self.min_temp)
            )
            await self._adax_data_handler.set_room_target_temperature(
                self._heater_data["id"], temperature, True
            )
        elif hvac_mode == HVAC_MODE_OFF:
            await self._adax_data_handler.set_room_target_temperature(
                self._heater_data["id"], self.min_temp, False
            )
        else:
            return
        await self._adax_data_handler.update()

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement which this device uses."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature."""
        return 5

    @property
    def max_temp(self) -> int:
        """Return the maximum temperature."""
        return 35

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._heater_data.get("temperature")

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature we try to reach."""
        return self._heater_data.get("targetTemperature")

    @property
    def target_temperature_step(self) -> int:
        """Return the supported step of target temperature."""
        return PRECISION_WHOLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._adax_data_handler.set_room_target_temperature(
            self._heater_data["id"], temperature, True
        )

    async def async_update(self) -> None:
        """Get the latest data."""
        for room in await self._adax_data_handler.get_rooms():
            if room["id"] == self._heater_data["id"]:
                self._heater_data = room
                return
