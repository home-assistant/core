"""Support for Broadlink climate devices."""
from typing import Any

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DOMAINS_AND_TYPES
from .device import BroadlinkDevice
from .entity import BroadlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink climate entities."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type in DOMAINS_AND_TYPES[Platform.CLIMATE]:
        async_add_entities([BroadlinkThermostat(device)])


class BroadlinkThermostat(ClimateEntity, BroadlinkEntity):
    """Representation of a Broadlink Hysen climate entity."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the climate entity."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id
        self._attr_hvac_mode = None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self._device.async_request(self._device.api.set_temp, temperature)
        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    @callback
    def _update_state(self, data: dict[str, Any]) -> None:
        """Update data."""
        if data.get("power"):
            if data.get("auto_mode"):
                self._attr_hvac_mode = HVACMode.AUTO
            else:
                self._attr_hvac_mode = HVACMode.HEAT

            if data.get("active"):
                self._attr_hvac_action = HVACAction.HEATING
            else:
                self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF

        self._attr_current_temperature = data.get("room_temp")
        self._attr_target_temperature = data.get("thermostat_temp")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._device.async_request(self._device.api.set_power, 0)
        else:
            await self._device.async_request(self._device.api.set_power, 1)
            mode = 0 if hvac_mode == HVACMode.HEAT else 1
            await self._device.async_request(self._device.api.set_mode, mode, 0)

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
