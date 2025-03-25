"""Support for Huum wifi-enabled sauna."""

from __future__ import annotations

import logging
from typing import Any

from huum.const import SaunaStatus
from huum.exceptions import SafetyException
from huum.huum import Huum
from huum.schemas import HuumStatusResponse

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Huum sauna with config flow."""
    huum_handler = hass.data.setdefault(DOMAIN, {})[entry.entry_id]

    async_add_entities([HuumDevice(huum_handler, entry.entry_id)], True)


class HuumDevice(ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 110
    _attr_min_temp = 40
    _attr_has_entity_name = True
    _attr_name = None

    _target_temperature: int | None = None
    _status: HuumStatusResponse | None = None

    def __init__(self, huum_handler: Huum, unique_id: str) -> None:
        """Initialize the heater."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name="Huum sauna",
            manufacturer="Huum",
        )

        self._huum_handler = huum_handler

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if self._status and self._status.status == SaunaStatus.ONLINE_HEATING:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def icon(self) -> str:
        """Return nice icon for heater."""
        if self.hvac_mode == HVACMode.HEAT:
            return "mdi:radiator"
        return "mdi:radiator-off"

    @property
    def current_temperature(self) -> int | None:
        """Return the current temperature."""
        if (status := self._status) is not None:
            return status.temperature
        return None

    @property
    def target_temperature(self) -> int:
        """Return the temperature we try to reach."""
        return self._target_temperature or int(self.min_temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await self._turn_on(self.target_temperature)
        elif hvac_mode == HVACMode.OFF:
            await self._huum_handler.turn_off()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temperature = temperature

        if self.hvac_mode == HVACMode.HEAT:
            await self._turn_on(temperature)

    async def async_update(self) -> None:
        """Get the latest status data.

        We get the latest status first from the status endpoints of the sauna.
        If that data does not include the temperature, that means that the sauna
        is off, we then call the off command which will in turn return the temperature.
        This is a workaround for getting the temperature as the Huum API does not
        return the target temperature of a sauna that is off, even if it can have
        a target temperature at that time.
        """
        self._status = await self._huum_handler.status_from_status_or_stop()
        if self._target_temperature is None or self.hvac_mode == HVACMode.HEAT:
            self._target_temperature = self._status.target_temperature

    async def _turn_on(self, temperature: int) -> None:
        try:
            await self._huum_handler.turn_on(temperature)
        except (ValueError, SafetyException) as err:
            _LOGGER.error(str(err))
            raise HomeAssistantError(f"Unable to turn on sauna: {err}") from err
