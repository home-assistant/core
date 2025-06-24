"""Support for OSO Energy water heaters."""

import datetime as dt
from typing import Any

from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.const import OSOEnergyWaterHeaterData
import voluptuous as vol

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DOMAIN
from .entity import OSOEnergyEntity

ATTR_UNTIL_TEMP_LIMIT = "until_temp_limit"
ATTR_V40MIN = "v40_min"
CURRENT_OPERATION_MAP: dict[str, Any] = {
    "default": {
        "off": STATE_OFF,
        "powersave": STATE_OFF,
        "extraenergy": STATE_HIGH_DEMAND,
    },
    "oso": {
        "auto": STATE_ECO,
        "off": STATE_OFF,
        "powersave": STATE_OFF,
        "extraenergy": STATE_HIGH_DEMAND,
    },
}
SERVICE_GET_PROFILE = "get_profile"
SERVICE_SET_PROFILE = "set_profile"
SERVICE_SET_V40MIN = "set_v40_min"
SERVICE_TURN_OFF = "turn_off"
SERVICE_TURN_ON = "turn_on"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OSO Energy heater based on a config entry."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("water_heater")
    if not devices:
        return
    async_add_entities((OSOEnergyWaterHeater(osoenergy, dev) for dev in devices), True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_GET_PROFILE,
        {},
        OSOEnergyWaterHeater.async_get_profile.__name__,
        supports_response=SupportsResponse.ONLY,
    )

    service_set_profile_schema = cv.make_entity_service_schema(
        {
            vol.Optional(f"hour_{hour:02d}"): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=75)
            )
            for hour in range(24)
        }
    )

    platform.async_register_entity_service(
        SERVICE_SET_PROFILE,
        service_set_profile_schema,
        OSOEnergyWaterHeater.async_set_profile.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_SET_V40MIN,
        {
            vol.Required(ATTR_V40MIN): vol.All(
                vol.Coerce(float), vol.Range(min=200, max=550)
            ),
        },
        OSOEnergyWaterHeater.async_set_v40_min.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_TURN_OFF,
        {vol.Required(ATTR_UNTIL_TEMP_LIMIT): vol.All(cv.boolean)},
        OSOEnergyWaterHeater.async_oso_turn_off.__name__,
    )

    platform.async_register_entity_service(
        SERVICE_TURN_ON,
        {vol.Required(ATTR_UNTIL_TEMP_LIMIT): vol.All(cv.boolean)},
        OSOEnergyWaterHeater.async_oso_turn_on.__name__,
    )


def _get_utc_hour(local_hour: int) -> dt.datetime:
    """Convert the requested local hour to a utc hour for the day.

    Args:
        local_hour: the local hour (0-23) for the current day to be converted.

    Returns:
        Datetime representation for the requested hour in utc time for the day.

    """
    now = dt_util.now()
    local_time = now.replace(hour=local_hour, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(local_time)


def _get_local_hour(utc_hour: int) -> dt.datetime:
    """Convert the requested utc hour to a local hour for the day.

    Args:
        utc_hour: the utc hour (0-23) for the current day to be converted.

    Returns:
        Datetime representation for the requested hour in local time for the day.

    """
    utc_now = dt_util.utcnow()
    utc_time = utc_now.replace(hour=utc_hour, minute=0, second=0, microsecond=0)
    return dt_util.as_local(utc_time)


def _convert_profile_to_local(values: list[float]) -> list[JsonValueType]:
    """Convert UTC profile to local.

    Receives a device temperature schedule - 24 values for the day where the index represents the hour of the day in UTC.
    Converts the schedule to local time.

    Args:
        values: list of floats representing the 24 hour temperature schedule for the device
    Returns:
        The device temperature schedule in local time.

    """
    profile: list[JsonValueType] = [0.0] * 24
    for hour in range(24):
        local_hour = _get_local_hour(hour)
        profile[local_hour.hour] = float(values[hour])

    return profile


class OSOEnergyWaterHeater(
    OSOEnergyEntity[OSOEnergyWaterHeaterData], WaterHeaterEntity
):
    """OSO Energy Water Heater Device."""

    _attr_name = None
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        instance: OSOEnergy,
        entity_data: OSOEnergyWaterHeaterData,
    ) -> None:
        """Initialize the OSO Energy water heater."""
        super().__init__(instance, entity_data)
        self._attr_unique_id = entity_data.device_id

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.entity_data.available

    @property
    def current_operation(self) -> str:
        """Return current operation."""
        status = self.entity_data.current_operation
        if status == "off":
            return STATE_OFF

        optimization_mode = self.entity_data.optimization_mode.lower()
        heater_mode = self.entity_data.heater_mode.lower()
        if optimization_mode in CURRENT_OPERATION_MAP:
            return CURRENT_OPERATION_MAP[optimization_mode].get(
                heater_mode, STATE_ELECTRIC
            )

        return CURRENT_OPERATION_MAP["default"].get(heater_mode, STATE_ELECTRIC)

    @property
    def current_temperature(self) -> float:
        """Return the current temperature of the heater."""
        return self.entity_data.current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.entity_data.target_temperature

    @property
    def target_temperature_high(self) -> float:
        """Return the temperature we try to reach."""
        return self.entity_data.target_temperature_high

    @property
    def target_temperature_low(self) -> float:
        """Return the temperature we try to reach."""
        return self.entity_data.target_temperature_low

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.entity_data.min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.entity_data.max_temperature

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on hotwater."""
        await self.osoenergy.hotwater.turn_on(self.entity_data, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off hotwater."""
        await self.osoenergy.hotwater.turn_off(self.entity_data, True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = int(kwargs.get("temperature", self.target_temperature))
        profile = [target_temperature] * 24

        await self.osoenergy.hotwater.set_profile(self.entity_data, profile)

    async def async_get_profile(self) -> ServiceResponse:
        """Return the current temperature profile of the device."""

        profile = self.entity_data.profile
        return {"profile": _convert_profile_to_local(profile)}

    async def async_set_profile(self, **kwargs: Any) -> None:
        """Handle the service call."""
        profile = self.entity_data.profile

        for hour in range(24):
            hour_key = f"hour_{hour:02d}"

            if hour_key in kwargs:
                profile[_get_utc_hour(hour).hour] = kwargs[hour_key]

        await self.osoenergy.hotwater.set_profile(self.entity_data, profile)

    async def async_set_v40_min(self, v40_min) -> None:
        """Handle the service call."""
        await self.osoenergy.hotwater.set_v40_min(self.entity_data, v40_min)

    async def async_oso_turn_off(self, until_temp_limit) -> None:
        """Handle the service call."""
        await self.osoenergy.hotwater.turn_off(self.entity_data, until_temp_limit)

    async def async_oso_turn_on(self, until_temp_limit) -> None:
        """Handle the service call."""
        await self.osoenergy.hotwater.turn_on(self.entity_data, until_temp_limit)

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.osoenergy.session.update_data()
        self.entity_data = await self.osoenergy.hotwater.get_water_heater(
            self.entity_data
        )
