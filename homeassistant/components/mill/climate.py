"""Support for mill wifi-enabled home heaters."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from mill import Heater, Mill
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_ON,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_AWAY_TEMP,
    ATTR_COMFORT_TEMP,
    ATTR_ROOM_NAME,
    ATTR_SLEEP_TEMP,
    DOMAIN,
    MANUFACTURER,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_SET_ROOM_TEMP,
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

SET_ROOM_TEMP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROOM_NAME): cv.string,
        vol.Optional(ATTR_AWAY_TEMP): cv.positive_int,
        vol.Optional(ATTR_COMFORT_TEMP): cv.positive_int,
        vol.Optional(ATTR_SLEEP_TEMP): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[Iterable[Entity]], None],
) -> None:
    """Set up the Mill climate."""
    mill_data_connection = Mill(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
    )
    if not await mill_data_connection.connect():
        raise ConfigEntryNotReady

    await mill_data_connection.find_all_heaters()

    dev = []
    for heater in mill_data_connection.heaters.values():
        dev.append(MillHeater(heater, mill_data_connection))
    async_add_entities(dev)

    async def set_room_temp(service: ServiceCall) -> None:
        """Set room temp."""
        room_name = service.data.get(ATTR_ROOM_NAME)
        sleep_temp = service.data.get(ATTR_SLEEP_TEMP)
        comfort_temp = service.data.get(ATTR_COMFORT_TEMP)
        away_temp = service.data.get(ATTR_AWAY_TEMP)
        await mill_data_connection.set_room_temperatures_by_name(
            room_name, sleep_temp, comfort_temp, away_temp
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM_TEMP, set_room_temp, schema=SET_ROOM_TEMP_SCHEMA
    )


class MillHeater(ClimateEntity):
    """Representation of a Mill Thermostat device."""

    def __init__(self, heater: Heater, mill_data_connection: Mill) -> None:
        """Initialize the thermostat."""
        self._heater = heater
        self._conn = mill_data_connection

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self) -> Any:
        """Return True if entity is available."""
        return self._heater.available

    @property
    def unique_id(self) -> Any:
        """Return a unique ID."""
        return self._heater.device_id

    @property
    def name(self) -> Any:
        """Return the name of the entity."""
        return self._heater.name

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        res = {
            "open_window": self._heater.open_window,
            "heating": self._heater.is_heating,
            "controlled_by_tibber": self._heater.tibber_control,
            "heater_generation": 1 if self._heater.is_gen1 else 2,
            "consumption_today": self._heater.day_consumption,
            "consumption_total": self._heater.total_consumption,
        }
        if self._heater.room:
            res["room"] = self._heater.room.name
            res["avg_room_temp"] = self._heater.room.avg_temp
        else:
            res["room"] = "Independent device"
        return res

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self) -> Any:
        """Return the temperature we try to reach."""
        return self._heater.set_temp

    @property
    def target_temperature_step(self) -> int:
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self) -> Any:
        """Return the current temperature."""
        return self._heater.current_temp

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        return FAN_ON if self._heater.fan_status == 1 else HVAC_MODE_OFF

    @property
    def fan_modes(self) -> list[str]:
        """List of available fan modes."""
        return [FAN_ON, HVAC_MODE_OFF]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def hvac_action(self) -> str:
        """Return current hvac i.e. heat, cool, idle."""
        if self._heater.is_gen1 or self._heater.is_heating == 1:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._heater.is_gen1 or self._heater.power_status == 1:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        if self._heater.is_gen1:
            return [HVAC_MODE_HEAT]
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._conn.set_heater_temp(self._heater.device_id, int(temperature))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan_status = 1 if fan_mode == FAN_ON else 0
        await self._conn.heater_control(self._heater.device_id, fan_status=fan_status)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            await self._conn.heater_control(self._heater.device_id, power_status=1)
        elif hvac_mode == HVAC_MODE_OFF and not self._heater.is_gen1:
            await self._conn.heater_control(self._heater.device_id, power_status=0)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        self._heater = await self._conn.update_device(self._heater.device_id)

    @property
    def device_id(self) -> Any:
        """Return the ID of the physical device this sensor is part of."""
        return self._heater.device_id

    @property
    def device_info(self) -> dict[str, str]:
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": f"generation {1 if self._heater.is_gen1 else 2}",
        }
        return device_info
