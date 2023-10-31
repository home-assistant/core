"""Ventilation Units from Komfovent integration."""
from __future__ import annotations

import komfovent_api

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

HASS_TO_KOMFOVENT_MODES = {
    HVACMode.COOL: komfovent_api.KomfoventModes.COOL,
    HVACMode.HEAT_COOL: komfovent_api.KomfoventModes.HEAT_COOL,
    HVACMode.OFF: komfovent_api.KomfoventModes.OFF,
    HVACMode.AUTO: komfovent_api.KomfoventModes.AUTO,
}
KOMFOVENT_TO_HASS_MODES = {v: k for k, v in HASS_TO_KOMFOVENT_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent unit control."""
    credentials, settings = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KomfoventDevice(credentials, settings)], True)


class KomfoventDevice(ClimateEntity):
    """Representation of a ventilation unit."""

    _attr_hvac_modes = list(HASS_TO_KOMFOVENT_MODES.keys())
    _attr_preset_modes = [mode.name for mode in komfovent_api.KomfoventPresets]
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        credentials: komfovent_api.KomfoventCredentials,
        settings: komfovent_api.KomfoventSettings,
    ) -> None:
        """Initialize the ventilation unit."""
        self._komfovent_credentials = credentials
        self._komfovent_settings = settings

        self._attr_unique_id = settings.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, settings.serial_number)},
            model=settings.model,
            name=settings.name,
            serial_number=settings.serial_number,
            sw_version=settings.version,
            manufacturer="Komfovent",
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        await komfovent_api.set_preset(
            self._komfovent_credentials,
            komfovent_api.KomfoventPresets[preset_mode],
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await komfovent_api.set_mode(
            self._komfovent_credentials, HASS_TO_KOMFOVENT_MODES[hvac_mode]
        )

    async def async_update(self) -> None:
        """Get the latest data."""
        result, status = await komfovent_api.get_unit_status(
            self._komfovent_credentials
        )
        if result != komfovent_api.KomfoventConnectionResult.SUCCESS or not status:
            self._attr_available = False
            return
        self._attr_available = True
        self._attr_preset_mode = status.preset
        self._attr_current_temperature = status.temp_extract
        self._attr_hvac_mode = KOMFOVENT_TO_HASS_MODES[status.mode]
