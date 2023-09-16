"""Support for Adax wifi-enabled home heaters."""
from __future__ import annotations

from typing import Any, cast

from adax import Adax
from adax_local import Adax as AdaxLocal

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACCOUNT_ID, CONNECTION_TYPE, DOMAIN, LOCAL


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Adax thermostat with config flow."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        adax_data_handler = AdaxLocal(
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_TOKEN],
            websession=async_get_clientsession(hass, verify_ssl=False),
        )
        async_add_entities(
            [LocalAdaxDevice(adax_data_handler, entry.data[CONF_UNIQUE_ID])], True
        )
        return

    adax_data_handler = Adax(
        entry.data[ACCOUNT_ID],
        entry.data[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
    )

    async_add_entities(
        (
            AdaxDevice(room, adax_data_handler)
            for room in await adax_data_handler.get_rooms()
        ),
        True,
    )


class AdaxDevice(ClimateEntity):
    """Representation of a heater."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, heater_data: dict[str, Any], adax_data_handler: Adax) -> None:
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
        if hvac_mode == HVACMode.HEAT:
            temperature = max(self.min_temp, self.target_temperature or self.min_temp)
            await self._adax_data_handler.set_room_target_temperature(
                self._device_id, temperature, True
            )
        elif hvac_mode == HVACMode.OFF:
            await self._adax_data_handler.set_room_target_temperature(
                self._device_id, self.min_temp, False
            )
        else:
            return
        await self._adax_data_handler.update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._adax_data_handler.set_room_target_temperature(
            self._device_id, temperature, True
        )

    async def async_update(self) -> None:
        """Get the latest data."""
        for room in await self._adax_data_handler.get_rooms():
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

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, adax_data_handler, unique_id):
        """Initialize the heater."""
        self._adax_data_handler = adax_data_handler
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Adax",
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._adax_data_handler.set_target_temperature(temperature)

    async def async_update(self) -> None:
        """Get the latest data."""
        data = await self._adax_data_handler.get_status()
        self._attr_target_temperature = data["target_temperature"]
        self._attr_current_temperature = data["current_temperature"]
        self._attr_available = self._attr_current_temperature is not None
