"""Support for OSO Energy water heaters."""
import voluptuous as vol

from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import OSOEnergyEntity, refresh_system
from .const import (
    ATTR_FULL_UTILIZATION,
    ATTR_PROFILE_HOURS,
    ATTR_V40MIN,
    DOMAIN,
    EXTRA_HEATER_ATTR,
    HEATER_MAX_TEMP,
    HEATER_MIN_TEMP,
    MANUFACTURER,
    OPERATION_LIST,
    OSO_ENERGY_TO_HASS_STATE,
    SERVICE_SET_PROFILE,
    SERVICE_SET_V40MIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SUPPORT_FLAGS_HEATER,
    SUPPORT_WATER_HEATER,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OSO Energy heater based on a config entry."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("water_heater")
    entities = []
    if devices:
        for dev in devices:
            entities.append(OSOEnergyWaterHeater(osoenergy, dev))
    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_TURN_ON,
        {vol.Required(ATTR_FULL_UTILIZATION): vol.All(cv.boolean)},
        "async_oso_turn_on",
    )

    platform.async_register_entity_service(
        SERVICE_TURN_OFF,
        {vol.Required(ATTR_FULL_UTILIZATION): vol.All(cv.boolean)},
        "async_oso_turn_off",
    )

    platform.async_register_entity_service(
        SERVICE_SET_V40MIN,
        {vol.Required(ATTR_V40MIN): vol.Coerce(float)},
        "async_set_v40_min",
    )

    platform.async_register_entity_service(
        SERVICE_SET_PROFILE,
        {
            vol.Required(ATTR_PROFILE_HOURS["00"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["01"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["02"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["03"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["04"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["05"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["06"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["07"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["08"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["09"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["10"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["11"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["12"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["13"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["14"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["15"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["16"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["17"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["18"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["19"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["20"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["21"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["22"]): vol.Coerce(int),
            vol.Required(ATTR_PROFILE_HOURS["23"]): vol.Coerce(int),
        },
        "async_set_profile",
    )


def _get_utc_hour(local_hour: int):
    """Get the utc hour."""
    now = dt_util.now()
    local_time = now.replace(hour=local_hour, minute=0, second=0, microsecond=0)
    utc_hour = dt_util.as_utc(local_time)
    return utc_hour.hour


def _get_local_hour(utc_hour: int):
    """Get the utc hour."""
    now = dt_util.utcnow()
    now_local = dt_util.now()
    utc_time = now.replace(hour=utc_hour, minute=0, second=0, microsecond=0)
    local_hour = dt_util.as_local(utc_time)
    local_hour = local_hour.replace(day=now_local.day)
    return local_hour


def _convert_profile_to_local(values):
    """Convert UTC profile to local."""
    profile = [None] * 24
    for hour in range(24):
        local_hour = _get_local_hour(hour)
        local_hour_string = local_hour.strftime("%Y-%m-%dT%H:%M:%S%z")
        profile[local_hour.hour] = {local_hour_string: values[hour]}

    return profile


class OSOEnergyWaterHeater(OSOEnergyEntity, WaterHeaterEntity):
    """OSO Energy Water Heater Device."""

    _attr_operation_list = OPERATION_LIST
    _attr_supported_features = SUPPORT_FLAGS_HEATER
    _attr_temperature_unit = TEMP_CELSIUS

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            manufacturer=MANUFACTURER,
            model=self.device["device_type"],
            name=self.device["device_name"],
        )

    @property
    def name(self):
        """Return the name of the water heater."""
        return self.device["device_name"]

    @property
    def available(self):
        """Return if the device is available."""
        return self.device.get("attributes", {}).get("available", False)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation."""
        return OSO_ENERGY_TO_HASS_STATE[self.device["status"]["current_operation"]]

    @property
    def operation_list(self):
        """List of available operation modes."""
        return SUPPORT_WATER_HEATER

    @property
    def current_temperature(self):
        """Return the current temperature of the heater."""
        return self.device.get("attributes", {}).get("current_temperature", 0)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.device.get("attributes", {}).get("target_temperature", 0)

    @property
    def target_temperature_high(self):
        """Return the temperature we try to reach."""
        return self.device.get("attributes", {}).get("target_temperature_high", 0)

    @property
    def target_temperature_low(self):
        """Return the temperature we try to reach."""
        return self.device.get("attributes", {}).get("target_temperature_low", 0)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.device.get("attributes", {}).get("min_temperature", HEATER_MIN_TEMP)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.device.get("attributes", {}).get("max_temperature", HEATER_MAX_TEMP)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {"integration": DOMAIN}

        for attribute, ha_name in EXTRA_HEATER_ATTR.items():
            value = self.device.get("attributes", {}).get(attribute)
            final = value
            if attribute == "profile":
                final = _convert_profile_to_local(value)

            attr.update({ha_name: final})

        return attr

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Turn on hotwater."""
        await self.osoenergy.hotwater.turn_on(self.device, True)

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn on hotwater."""
        await self.osoenergy.hotwater.turn_off(self.device, True)

    @refresh_system
    async def async_oso_turn_on(self, full_utilization):
        """Handle the service call."""
        await self.osoenergy.hotwater.turn_on(self.device, full_utilization)

    @refresh_system
    async def async_oso_turn_off(self, full_utilization):
        """Handle the service call."""
        await self.osoenergy.hotwater.turn_off(self.device, full_utilization)

    @refresh_system
    async def async_set_v40_min(self, v40_min):
        """Handle the service call."""
        await self.osoenergy.hotwater.set_v40_min(self.device, v40_min)

    @refresh_system
    async def async_set_profile(
        self,
        hour_00,
        hour_01,
        hour_02,
        hour_03,
        hour_04,
        hour_05,
        hour_06,
        hour_07,
        hour_08,
        hour_09,
        hour_10,
        hour_11,
        hour_12,
        hour_13,
        hour_14,
        hour_15,
        hour_16,
        hour_17,
        hour_18,
        hour_19,
        hour_20,
        hour_21,
        hour_22,
        hour_23,
    ):
        """Handle the service call."""
        profile = [None] * 24
        profile[_get_utc_hour(0)] = hour_00
        profile[_get_utc_hour(1)] = hour_01
        profile[_get_utc_hour(2)] = hour_02
        profile[_get_utc_hour(3)] = hour_03
        profile[_get_utc_hour(4)] = hour_04
        profile[_get_utc_hour(5)] = hour_05
        profile[_get_utc_hour(6)] = hour_06
        profile[_get_utc_hour(7)] = hour_07
        profile[_get_utc_hour(8)] = hour_08
        profile[_get_utc_hour(9)] = hour_09
        profile[_get_utc_hour(10)] = hour_10
        profile[_get_utc_hour(11)] = hour_11
        profile[_get_utc_hour(12)] = hour_12
        profile[_get_utc_hour(13)] = hour_13
        profile[_get_utc_hour(14)] = hour_14
        profile[_get_utc_hour(15)] = hour_15
        profile[_get_utc_hour(16)] = hour_16
        profile[_get_utc_hour(17)] = hour_17
        profile[_get_utc_hour(18)] = hour_18
        profile[_get_utc_hour(19)] = hour_19
        profile[_get_utc_hour(20)] = hour_20
        profile[_get_utc_hour(21)] = hour_21
        profile[_get_utc_hour(22)] = hour_22
        profile[_get_utc_hour(23)] = hour_23

        await self.osoenergy.hotwater.set_profile(self.device, profile)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.osoenergy.session.update_data()
        self.device = await self.osoenergy.hotwater.get_water_heater(self.device)
