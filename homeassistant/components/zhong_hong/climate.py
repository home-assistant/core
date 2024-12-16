"""Support for ZhongHong HVAC Controller."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zhong_hong_hvac.hub import ZhongHongGateway
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_GATEWAY_ADDRRESS = "gateway_address"

DEFAULT_PORT = 9999
DEFAULT_GATEWAY_ADDRRESS = 1

SIGNAL_DEVICE_ADDED = "zhong_hong_device_added"
SIGNAL_ZHONG_HONG_HUB_START = "zhong_hong_hub_start"

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_GATEWAY_ADDRRESS, default=DEFAULT_GATEWAY_ADDRRESS
        ): cv.positive_int,
    }
)

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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZhongHong HVAC platform."""

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    gw_addr = config.get(CONF_GATEWAY_ADDRRESS)
    hub = ZhongHongGateway(host, port, gw_addr)
    devices = [
        ZhongHongClimate(hub, addr_out, addr_in)
        for (addr_out, addr_in) in hub.discovery_ac()
    ]

    _LOGGER.debug("We got %s zhong_hong climate devices", len(devices))

    hub_is_initialized = False

    def _start_hub():
        """Start the hub socket and query status of all devices."""
        hub.start_listen()
        hub.query_all_status()

    async def startup():
        """Start hub socket after all climate entity is set up."""
        nonlocal hub_is_initialized
        if not all(device.is_initialized for device in devices):
            return

        if hub_is_initialized:
            return

        _LOGGER.debug("zhong_hong hub start listen event")
        await hass.async_add_executor_job(_start_hub)
        hub_is_initialized = True

    async_dispatcher_connect(hass, SIGNAL_DEVICE_ADDED, startup)

    # add devices after SIGNAL_DEVICE_SETTED_UP event is listened
    add_entities(devices)

    def stop_listen(event):
        """Stop ZhongHongHub socket."""
        hub.stop_listen()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_listen)


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

    def __init__(self, hub, addr_out, addr_in):
        """Set up the ZhongHong climate devices."""

        self._device = ZhongHongHVAC(hub, addr_out, addr_in)
        self._hub = hub
        self._current_operation = None
        self._current_temperature = None
        self._target_temperature = None
        self._current_fan_mode = None
        self.is_initialized = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._device.register_update_callback(self._after_update)
        self.is_initialized = True
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADDED)

    def _after_update(self, climate):
        """Handle state update."""
        _LOGGER.debug("async update ha state")
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
    def name(self):
        """Return the name of the thermostat, if any."""
        return self.unique_id

    @property
    def unique_id(self):
        """Return the unique ID of the HVAC."""
        return f"zhong_hong_hvac_{self._device.addr_out}_{self._device.addr_in}"

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
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._device.fan_list

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._device.min_temp

    @property
    def max_temp(self):
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
        self._device.set_fan_mode(fan_mode)
