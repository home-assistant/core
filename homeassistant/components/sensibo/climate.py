"""Support for Sensibo wifi-enabled home thermostats."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import async_timeout
from pysensibo import SensiboClient, SensiboError
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
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
    "": HVAC_MODE_OFF,
}

HA_TO_SENSIBO = {value: key for key, value in SENSIBO_TO_HA.items()}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
    devices = data["devices"]

    entities = [
        SensiboClimate(client, dev, hass.config.units.temperature_unit)
        for dev in devices
    ]

    async_add_entities(entities)

    async def async_assume_state(service: ServiceCall) -> None:
        """Set state according to external service call.."""
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_climate = [
                entity for entity in entities if entity.entity_id in entity_ids
            ]
        else:
            target_climate = entities

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

    def __init__(self, client: SensiboClient, data: dict[str, Any], units: str) -> None:
        """Initiate SensiboClimate."""
        self._client = client
        self._id = data["id"]
        self._external_state = None
        self._units = units
        self._failed_update = False
        self._attr_available = False
        self._attr_unique_id = self._id
        self._attr_temperature_unit = (
            TEMP_CELSIUS if data["temperatureUnit"] == "C" else TEMP_FAHRENHEIT
        )
        self._do_update(data)
        self._attr_target_temperature_step = (
            1 if self.temperature_unit == units else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            name=self._attr_name,
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=data["productModel"],
            sw_version=data["firmwareVersion"],
            hw_version=data["firmwareType"],
            suggested_area=self._attr_name,
        )

    def _do_update(self, data) -> None:
        self._attr_name = data["room"]["name"]
        self._ac_states = data["acState"]
        self._attr_extra_state_attributes = {
            "battery": data["measurements"].get("batteryVoltage")
        }
        self._attr_current_temperature = convert_temperature(
            data["measurements"].get("temperature"),
            TEMP_CELSIUS,
            self._attr_temperature_unit,
        )
        self._attr_current_humidity = data["measurements"].get("humidity")

        self._attr_target_temperature = self._ac_states.get("targetTemperature")
        if self._ac_states["on"]:
            self._attr_hvac_mode = SENSIBO_TO_HA.get(self._ac_states["mode"], "")
        else:
            self._attr_hvac_mode = HVAC_MODE_OFF
        self._attr_fan_mode = self._ac_states.get("fanLevel")
        self._attr_swing_mode = self._ac_states.get("swing")

        self._attr_available = data["connectionStatus"].get("isAlive")
        capabilities = data["remoteCapabilities"]
        self._attr_hvac_modes = [SENSIBO_TO_HA[mode] for mode in capabilities["modes"]]
        self._attr_hvac_modes.append(HVAC_MODE_OFF)

        current_capabilities = capabilities["modes"][self._ac_states.get("mode")]
        self._attr_fan_modes = current_capabilities.get("fanLevels")
        self._attr_swing_modes = current_capabilities.get("swing")

        temperature_unit_key = data.get("temperatureUnit") or self._ac_states.get(
            "temperatureUnit"
        )
        if temperature_unit_key:
            self._temperature_unit = (
                TEMP_CELSIUS if temperature_unit_key == "C" else TEMP_FAHRENHEIT
            )
            self._temperatures_list = (
                current_capabilities["temperatures"]
                .get(temperature_unit_key, {})
                .get("values", [])
            )
        else:
            self._temperature_unit = self._units
            self._temperatures_list = []
        self._attr_min_temp = (
            self._temperatures_list[0] if self._temperatures_list else super().min_temp
        )
        self._attr_max_temp = (
            self._temperatures_list[-1] if self._temperatures_list else super().max_temp
        )
        self._attr_temperature_unit = self._temperature_unit

        self._attr_supported_features = 0
        for key in self._ac_states:
            if key in FIELD_TO_FLAG:
                self._attr_supported_features |= FIELD_TO_FLAG[key]

        self._attr_state = self._external_state or super().state

    async def async_set_temperature(self, **kwargs) -> None:
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

    async def async_set_fan_mode(self, fan_mode) -> None:
        """Set new target fan mode."""
        await self._async_set_ac_state_property("fanLevel", fan_mode)

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._async_set_ac_state_property("on", False)
            return

        # Turn on if not currently on.
        if not self._ac_states["on"]:
            await self._async_set_ac_state_property("on", True)

        await self._async_set_ac_state_property("mode", HA_TO_SENSIBO[hvac_mode])

    async def async_set_swing_mode(self, swing_mode) -> None:
        """Set new target swing operation."""
        await self._async_set_ac_state_property("swing", swing_mode)

    async def async_turn_on(self) -> None:
        """Turn Sensibo unit on."""
        await self._async_set_ac_state_property("on", True)

    async def async_turn_off(self) -> None:
        """Turn Sensibo unit on."""
        await self._async_set_ac_state_property("on", False)

    async def async_assume_state(self, state) -> None:
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

    async def async_update(self) -> None:
        """Retrieve latest state."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                data = await self._client.async_get_device(self._id, _FETCH_FIELDS)
        except (
            aiohttp.client_exceptions.ClientError,
            asyncio.TimeoutError,
            SensiboError,
        ) as err:
            if self._failed_update:
                _LOGGER.warning(
                    "Failed to update data for device '%s' from Sensibo servers with error %s",
                    self._attr_name,
                    err,
                )
                self._attr_available = False
                self.async_write_ha_state()
                return

            _LOGGER.debug("First failed update data for device '%s'", self._attr_name)
            self._failed_update = True
            return

        if self.temperature_unit == self.hass.config.units.temperature_unit:
            self._attr_target_temperature_step = 1
        else:
            self._attr_target_temperature_step = None

        self._failed_update = False
        self._do_update(data)

    async def _async_set_ac_state_property(
        self, name, value, assumed_state=False
    ) -> None:
        """Set AC state."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                await self._client.async_set_ac_state_property(
                    self._id, name, value, self._ac_states, assumed_state
                )
        except (
            aiohttp.client_exceptions.ClientError,
            asyncio.TimeoutError,
            SensiboError,
        ) as err:
            self._attr_available = False
            self.async_write_ha_state()
            raise Exception(
                f"Failed to set AC state for device {self._attr_name} to Sensibo servers"
            ) from err
