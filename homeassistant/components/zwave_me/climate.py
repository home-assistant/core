"""Representation of a thermostat."""
from __future__ import annotations

from zwave_me_ws import ZWaveMeData

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform

TEMPERATURE_DEFAULT_STEP = 0.5

DEVICE_NAME = ZWaveMePlatform.CLIMATE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""

    @callback
    def add_new_device(new_device: ZWaveMeData) -> None:
        """Add a new device."""
        controller = hass.data[DOMAIN][config_entry.entry_id]
        climate = ZWaveMeClimate(controller, new_device)

        async_add_entities(
            [
                climate,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeClimate(ZWaveMeEntity, ClimateEntity):
    """Representation of a ZWaveMe sensor."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        self.controller.zwave_api.send_command(
            self.device.id, f"exact?level={temperature}"
        )

    @property
    def temperature_unit(self) -> str:
        """Return the temperature_unit."""
        return self.device.scaleTitle

    @property
    def target_temperature(self) -> float:
        """Return the state of the sensor."""
        return self.device.level

    @property
    def max_temp(self) -> float:
        """Return min temperature for the device."""
        return self.device.max

    @property
    def min_temp(self) -> float:
        """Return max temperature for the device."""
        return self.device.min

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return TEMPERATURE_DEFAULT_STEP
