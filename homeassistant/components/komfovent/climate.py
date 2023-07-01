"""Ventilation Units from Komfovent integration."""
from __future__ import annotations

import komfovent_api

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PARAM_HOST, PARAM_PASSWORD, PARAM_USERNAME


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent unit control."""
    conf_host = str(entry.data[PARAM_HOST])
    conf_username = str(entry.data[PARAM_USERNAME])
    conf_password = str(entry.data[PARAM_PASSWORD])

    unit = await komfovent_api.create_unit(conf_host, conf_username, conf_password)
    async_add_entities([KomfoventDevice(unit)], True)


class KomfoventDevice(ClimateEntity):
    """Representation of a ventilation unit."""

    _attr_preset_modes = [
        "AWAY",
        "NORMAL",
        "INTENSIVE",
        "BOOST",
        "KITCHEN",
        "FIREPLACE",
        "OVERRIDE",
        "HOLIDAYS",
    ]
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, device) -> None:
        """Initialize the heater."""
        self._komfovent_device = device
        self._attr_unique_id = self._komfovent_device.get_id()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._attr_unique_id))},
            model=self._komfovent_device.get_model(),
            manufacturer="Komfovent",
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target temperature."""
        await self._komfovent_device.set_preset(preset_mode)

    async def async_update(self) -> None:
        """Get the latest data."""
        data = await self._komfovent_device.refresh()
        self._attr_available = data is not None
        if data is None:
            return
        self._attr_preset_mode = data["preset"]
        self._attr_current_temperature = data["current_temperature"]
