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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PARAM_HOST, PARAM_PASSWORD, PARAM_USERNAME, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent unit control."""
    conf_host = str(entry.data[PARAM_HOST])
    conf_username = str(entry.data[PARAM_USERNAME])
    conf_password = str(entry.data[PARAM_PASSWORD])
    _, credentials = komfovent_api.get_credentials(
        conf_host, conf_username, conf_password
    )

    result, settings = await komfovent_api.get_settings(credentials)
    if result == komfovent_api.KomfoventConnectionResult.SUCCESS:
        async_add_entities([KomfoventDevice(credentials, settings)], True)


class KomfoventDevice(ClimateEntity):
    """Representation of a ventilation unit."""

    _attr_hvac_modes = [HVACMode.FAN_ONLY]
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_preset_modes = [mode.name for mode in komfovent_api.KomfoventOperatingModes]
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "ventilation_unit"
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
            sw_version=settings.version,
            manufacturer=MANUFACTURER,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target temperature."""
        await komfovent_api.set_operating_mode(
            self._komfovent_credentials,
            komfovent_api.KomfoventOperatingModes[preset_mode],
        )

    async def async_update(self) -> None:
        """Get the latest data."""
        result, status = await komfovent_api.get_unit_status(
            self._komfovent_credentials
        )
        if result != komfovent_api.KomfoventConnectionResult.SUCCESS or status is None:
            self._attr_available = False
            return
        self._attr_available = True
        self._attr_preset_mode = status.mode
        self._attr_current_temperature = status.temp_extract
