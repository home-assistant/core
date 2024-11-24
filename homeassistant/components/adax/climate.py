"""Support for Adax wifi-enabled home heaters."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_UNIQUE_ID,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONNECTION_TYPE, DOMAIN, LOCAL
from .data_handler import AdaxDataHandler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Adax thermostat with config flow."""
    adax_data_handler = hass.data[entry.entry_id]
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        async_add_entities(
            [LocalAdaxDevice(adax_data_handler, entry.data[CONF_UNIQUE_ID])], True
        )
        return

    async_add_entities(
        (AdaxDevice(room, adax_data_handler) for room in adax_data_handler.get_rooms()),
        True,
    )


class AdaxDevice(ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, heater_data: dict[str, Any], adax_data_handler: AdaxDataHandler
    ) -> None:
        """Initialize the heater."""
        self._device_id = heater_data["id"]
        self._adax_data_handler = adax_data_handler

        self._attr_unique_id = f"{heater_data['homeId']}_{heater_data['id']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heater_data["id"])},
            # Instead of setting the device name to the entity name, adax
            # should be updated to set has_entity_name = True, and set the entity
            # name to None
            name=cast(str | None, self.name),
            manufacturer="Adax",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        adax = self._adax_data_handler.get_interface()
        if hvac_mode == HVACMode.HEAT:
            temperature = max(self.min_temp, self.target_temperature or self.min_temp)
            await adax.set_room_target_temperature(self._device_id, temperature, True)
        elif hvac_mode == HVACMode.OFF:
            await adax.set_room_target_temperature(
                self._device_id, self.min_temp, False
            )
        else:
            return
        await adax.update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        adax = self._adax_data_handler.get_interface()
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await adax.set_room_target_temperature(self._device_id, temperature, True)

    async def async_update(self) -> None:
        """Get the latest data."""
        await self._adax_data_handler.async_update()
        for room in self._adax_data_handler.get_rooms():
            if room is None:
                continue
            if room["id"] != self._device_id:
                continue
            self._attr_name = room["name"]
            self._attr_current_temperature = room.get("temperature")
            self._attr_target_temperature = room.get("targetTemperature")
            if room["heatingEnabled"]:
                self._attr_hvac_mode = HVACMode.HEAT
                self._attr_icon = "mdi:radiator"
            else:
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_icon = "mdi:radiator-off"
            return


class LocalAdaxDevice(ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, adax_data_handler: AdaxDataHandler, unique_id: str) -> None:
        """Initialize the heater."""
        self._adax_data_handler = adax_data_handler
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Adax",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        adax = self._adax_data_handler.get_interface()
        if hvac_mode == HVACMode.HEAT:
            temperature = self._attr_target_temperature or self._attr_min_temp
            await adax.set_target_temperature(temperature)
        elif hvac_mode == HVACMode.OFF:
            await adax.set_target_temperature(0)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        adax = self._adax_data_handler.get_interface()
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await adax.set_target_temperature(temperature)

    async def async_update(self) -> None:
        """Get the latest data."""
        adax = self._adax_data_handler.get_interface()
        data = await adax.get_status()
        self._attr_current_temperature = data["current_temperature"]
        self._attr_available = self._attr_current_temperature is not None
        if (target_temp := data["target_temperature"]) == 0:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_icon = "mdi:radiator-off"
            if target_temp == 0:
                self._attr_target_temperature = self._attr_min_temp
        else:
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_icon = "mdi:radiator"
            self._attr_target_temperature = target_temp
