"""Support for ZhongHong HVAC Controller."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PORT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

CONF_GATEWAY_ADDRESS = "gateway_address"

DEFAULT_PORT = 9999
DEFAULT_GATEWAY_ADDRESS = 1


_LOGGER = logging.getLogger(__name__)

ZHONG_HONG_MODE_COOL = "cool"
ZHONG_HONG_MODE_HEAT = "heat"
ZHONG_HONG_MODE_DRY = "dry"
ZHONG_HONG_MODE_FAN_ONLY = "fan_only"


MODE_TO_STATE = {
    ZHONG_HONG_MODE_COOL: HVACMode.COOL,
    ZHONG_HONG_MODE_HEAT: HVACMode.HEAT,
    ZHONG_HONG_MODE_DRY: HVACMode.DRY,
    ZHONG_HONG_MODE_FAN_ONLY: HVACMode.FAN_ONLY,
}

FAN_MODE_MAP = {
    FAN_LOW: "LOW",
    FAN_MEDIUM: "MID",
    FAN_HIGH: "HIGH",
    FAN_MIDDLE: "MID",
    "medium_high": "MIDHIGH",
    "medium_low": "MIDLOW",
}
FAN_MODE_REVERSE_MAP = {v: k for k, v in FAN_MODE_MAP.items()}


PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
        ): cv.positive_int,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZhongHong HVAC platform from legacy YAML."""
    _LOGGER.warning(
        "Configuration of the ZhongHong HVAC platform in YAML is deprecated "
        "and will be removed in a future release. Your configuration has been "
        "imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    coro = hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    asyncio.run_coroutine_threadsafe(coro, hass.loop)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZhongHong HVAC platform from a config entry."""

    entry_data = hass.data[DOMAIN][entry.entry_id]
    hub = entry_data["hub"]
    devices_discovered = entry_data["devices"]

    devices = [
        ZhongHongClimate(hub, addr_out, addr_in)
        for (addr_out, addr_in) in devices_discovered
    ]

    _LOGGER.debug("Adding %s zhong_hong climate devices", len(devices))
    async_add_entities(devices)


class ZhongHongClimate(ClimateEntity):
    """Representation of a ZhongHong controller support HVAC."""

    _attr_hvac_modes = [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    ]
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True  # Good practice for new integrations

    def __init__(self, hub, addr_out, addr_in):
        """Set up the ZhongHong climate devices."""
        self._device = ZhongHongHVAC(hub, addr_out, addr_in)
        self._hub = hub
        self._current_operation = None
        self._current_temperature = None
        self._target_temperature = None
        self._current_fan_mode = None

        self._attr_unique_id = (
            f"zhong_hong_hvac_{self._device.addr_out}_{self._device.addr_in}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": f"AC {self._device.addr_out}-{self._device.addr_in}",
            "manufacturer": "ZhongHong",
            "model": "HVAC Unit",
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._device.register_update_callback(self._after_update)

    def _after_update(self, climate):
        """Handle state update."""
        _LOGGER.debug("Async update for %s", self.entity_id)
        if self._device.current_operation:
            self._current_operation = MODE_TO_STATE[
                self._device.current_operation.lower()
            ]
        if self._device.current_temperature:
            self._current_temperature = self._device.current_temperature
        if self._device.current_fan_mode:
            self._current_fan_mode = self._device.current_fan_mode
        if self._device.target_temperature:
            self._target_temperature = self._device.target_temperature
        self.schedule_update_ha_state()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        if self.is_on:
            return self._current_operation
        return HVACMode.OFF

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def is_on(self):
        """Return true if on."""
        return self._device.is_on

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if not self._current_fan_mode:
            return None
        return FAN_MODE_REVERSE_MAP.get(self._current_fan_mode, self._current_fan_mode)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        if not self._device.fan_list:
            return []
        return list({FAN_MODE_REVERSE_MAP.get(x, x) for x in self._device.fan_list})

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.max_temp

    def turn_on(self) -> None:
        """Turn on ac."""
        return self._device.turn_on()

    def turn_off(self) -> None:
        """Turn off ac."""
        return self._device.turn_off()

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._device.set_temperature(temperature)

        if (operation_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self.set_hvac_mode(operation_mode)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            if self.is_on:
                self.turn_off()
            return

        if not self.is_on:
            self.turn_on()

        self._device.set_operation_mode(hvac_mode.upper())

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        mapped_mode = FAN_MODE_MAP.get(fan_mode)
        if not mapped_mode:
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
        self._device.set_fan_mode(mapped_mode)
