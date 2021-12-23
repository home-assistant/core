"""Support for Sensibo wifi-enabled home thermostats."""

import asyncio
import logging

import aiohttp
import async_timeout
import pysensibo
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    CONF_API_KEY,
    CONF_ID,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    ConfigType,
    DiscoveryInfoType,
)
from homeassistant.util.temperature import convert as convert_temperature

from .const import _FETCH_FIELDS, ALL, DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)

SERVICE_ASSUME_STATE = "assume_state"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, [cv.string]),
    }
)

ASSUME_STATE_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_ENTITY_ID): cv.entity_ids, vol.Required(ATTR_STATE): cv.string}
)

FIELD_TO_FLAG = {
    "fanLevel": SUPPORT_FAN_MODE,
    "swing": SUPPORT_SWING_MODE,
    "targetTemperature": SUPPORT_TARGET_TEMPERATURE,
}

SENSIBO_TO_HA = {
    "cool": HVAC_MODE_COOL,
    "heat": HVAC_MODE_HEAT,
    "fan": HVAC_MODE_FAN_ONLY,
    "auto": HVAC_MODE_HEAT_COOL,
    "dry": HVAC_MODE_DRY,
}

HA_TO_SENSIBO = {value: key for key, value in SENSIBO_TO_HA.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
):
    """Set up Sensibo devices."""
    _LOGGER.warning(
        "Loading Sensibo via platform setup is deprecated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Sensibo climate entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    devicelist = data["devices"]

    devices = [
        SensiboClimate(client, dev, hass.config.units.temperature_unit)
        for dev in devicelist
    ]

    async_add_entities(devices)

    async def async_assume_state(service):
        """Set state according to external service call.."""
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_climate = [
                device for device in devices if device.entity_id in entity_ids
            ]
        else:
            target_climate = devices

        update_tasks = []
        for climate in target_climate:
            await climate.async_assume_state(service.data.get(ATTR_STATE))
            update_tasks.append(climate.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSUME_STATE,
        async_assume_state,
        schema=ASSUME_STATE_SCHEMA,
    )


class SensiboClimate(ClimateEntity):
    """Representation of a Sensibo device."""

    def __init__(self, client, data, units):
        """Build SensiboClimate.

        client: aiohttp session.
        data: initially-fetched data.
        """
        self._client = client
        self._id = data["id"]
        self._external_state = None
        self._units = units
        self._available = False
        self._do_update(data)
        self._failed_update = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            name=self._name,
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=data["productModel"],
            sw_version=data["firmwareVersion"],
            hw_version=data["firmwareType"],
            suggested_area=self._name,
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    def _do_update(self, data):
        self._name = data["room"]["name"]
        self._measurements = data["measurements"]
        self._ac_states = data["acState"]
        self._available = data["connectionStatus"]["isAlive"]
        capabilities = data["remoteCapabilities"]
        self._operations = [SENSIBO_TO_HA[mode] for mode in capabilities["modes"]]
        self._operations.append(HVAC_MODE_OFF)
        self._current_capabilities = capabilities["modes"][self._ac_states["mode"]]
        temperature_unit_key = data.get("temperatureUnit") or self._ac_states.get(
            "temperatureUnit"
        )
        if temperature_unit_key:
            self._temperature_unit = (
                TEMP_CELSIUS if temperature_unit_key == "C" else TEMP_FAHRENHEIT
            )
            self._temperatures_list = (
                self._current_capabilities["temperatures"]
                .get(temperature_unit_key, {})
                .get("values", [])
            )
        else:
            self._temperature_unit = self._units
            self._temperatures_list = []
        self._supported_features = 0
        for key in self._ac_states:
            if key in FIELD_TO_FLAG:
                self._supported_features |= FIELD_TO_FLAG[key]

    @property
    def state(self):
        """Return the current state."""
        return self._external_state or super().state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"battery": self.current_battery}

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return self._temperature_unit

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._ac_states.get("targetTemperature")

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        if self.temperature_unit == self.hass.config.units.temperature_unit:
            # We are working in same units as the a/c unit. Use whole degrees
            # like the API supports.
            return 1
        # Unit conversion is going on. No point to stick to specific steps.
        return None

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if not self._ac_states["on"]:
            return HVAC_MODE_OFF
        return SENSIBO_TO_HA.get(self._ac_states["mode"])

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._measurements["humidity"]

    @property
    def current_battery(self):
        """Return the current battery voltage."""
        return self._measurements.get("batteryVoltage")

    @property
    def current_temperature(self):
        """Return the current temperature."""
        # This field is not affected by temperatureUnit.
        # It is always in C
        return convert_temperature(
            self._measurements["temperature"], TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._operations

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._ac_states.get("fanLevel")

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._current_capabilities.get("fanLevels")

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self._ac_states.get("swing")

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return self._current_capabilities.get("swing")

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return (
            self._temperatures_list[0] if self._temperatures_list else super().min_temp
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return (
            self._temperatures_list[-1] if self._temperatures_list else super().max_temp
        )

    @property
    def unique_id(self):
        """Return unique ID based on Sensibo ID."""
        return self._id

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        temperature = int(temperature)
        if temperature not in self._temperatures_list:
            # Requested temperature is not supported.
            if temperature == self.target_temperature:
                return
            index = self._temperatures_list.index(self.target_temperature)
            if (
                temperature > self.target_temperature
                and index < len(self._temperatures_list) - 1
            ):
                temperature = self._temperatures_list[index + 1]
            elif temperature < self.target_temperature and index > 0:
                temperature = self._temperatures_list[index - 1]
            else:
                return

        await self._async_set_ac_state_property("targetTemperature", temperature)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self._async_set_ac_state_property("fanLevel", fan_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._async_set_ac_state_property("on", False)
            return

        # Turn on if not currently on.
        if not self._ac_states["on"]:
            await self._async_set_ac_state_property("on", True)

        await self._async_set_ac_state_property("mode", HA_TO_SENSIBO[hvac_mode])

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        await self._async_set_ac_state_property("swing", swing_mode)

    async def async_turn_on(self):
        """Turn Sensibo unit on."""
        await self._async_set_ac_state_property("on", True)

    async def async_turn_off(self):
        """Turn Sensibo unit on."""
        await self._async_set_ac_state_property("on", False)

    async def async_assume_state(self, state):
        """Set external state."""
        change_needed = (state != HVAC_MODE_OFF and not self._ac_states["on"]) or (
            state == HVAC_MODE_OFF and self._ac_states["on"]
        )

        if change_needed:
            await self._async_set_ac_state_property("on", state != HVAC_MODE_OFF, True)

        if state in (STATE_ON, HVAC_MODE_OFF):
            self._external_state = None
        else:
            self._external_state = state

    async def async_update(self):
        """Retrieve latest state."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                data = await self._client.async_get_device(self._id, _FETCH_FIELDS)
        except (
            aiohttp.client_exceptions.ClientError,
            asyncio.TimeoutError,
            pysensibo.SensiboError,
        ):
            if self._failed_update:
                _LOGGER.warning(
                    "Failed to update data for device '%s' from Sensibo servers",
                    self.name,
                )
                self._available = False
                self.async_write_ha_state()
                return

            _LOGGER.debug("First failed update data for device '%s'", self.name)
            self._failed_update = True
            return

        self._failed_update = False
        self._do_update(data)

    async def _async_set_ac_state_property(self, name, value, assumed_state=False):
        """Set AC state."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                await self._client.async_set_ac_state_property(
                    self._id, name, value, self._ac_states, assumed_state
                )
        except (
            aiohttp.client_exceptions.ClientError,
            asyncio.TimeoutError,
            pysensibo.SensiboError,
        ) as err:
            self._available = False
            self.async_write_ha_state()
            raise Exception(
                f"Failed to set AC state for device {self.name} to Sensibo servers"
            ) from err
