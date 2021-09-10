"""Support for the Escea HVAC."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from pescea import Controller

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_EXCLUDE,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    ESCEA,
)

_LOGGER = logging.getLogger(__name__)

_ESCEA_FAN_TO_HA = {
    Controller.Fan.FLAME_EFFECT: FAN_LOW,
    Controller.Fan.FAN_BOOST: FAN_HIGH,
    Controller.Fan.AUTO: FAN_AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigType, async_add_entities: Callable
):
    """Initialize an Escea Controller."""
    disco = hass.data[DATA_DISCOVERY_SERVICE]

    @callback
    def init_controller(ctrl: Controller):
        """Register the controller device."""
        conf: ConfigType = hass.data.get(DATA_CONFIG)

        # Filter out any entities excluded in the config file
        if conf and ctrl.device_uid in conf[CONF_EXCLUDE]:
            _LOGGER.info("Controller UID=%s ignored as excluded", ctrl.device_uid)
            return
        _LOGGER.info("Controller UID=%s discovered", ctrl.device_uid)

        device = ControllerDevice(ctrl)
        async_add_entities([device])

    # create any components not yet created
    for controller in disco.pi_disco.controllers.values():
        init_controller(controller)

    # connect to register any further components
    async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, init_controller)

    return True


def _return_on_connection_error(ret: Any = None):
    def wrap(func: Callable):
        def wrapped_f(*args, **kwargs):
            if not args[0].available:
                return ret
            try:
                return func(*args, **kwargs)
            except ConnectionError:
                return ret

        return wrapped_f

    return wrap


class ControllerDevice(ClimateEntity):
    """Representation of Escea Controller."""

    def __init__(self, controller: Controller) -> None:
        """Initialise ControllerDevice."""
        self._controller = controller

        self._supported_features = SUPPORT_FAN_MODE
        self._supported_features |= SUPPORT_TARGET_TEMPERATURE

        self._fan_to_pescea = {}
        for fan in controller.Fan:
            self._fan_to_pescea[_ESCEA_FAN_TO_HA[fan]] = fan
        self._available = True

        self._device_info = {
            "identifiers": {(ESCEA, self.unique_id)},
            "name": self.name,
            "manufacturer": "Escea",
        }

    async def async_added_to_hass(self):
        """Call on adding to hass."""
        # Register for connect/disconnect/update events
        @callback
        def controller_disconnected(ctrl: Controller, ex: Exception) -> None:
            """Disconnected from controller."""
            if ctrl is not self._controller:
                return
            self.set_available(False, ex)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_DISCONNECTED, controller_disconnected
            )
        )

        @callback
        def controller_reconnected(ctrl: Controller) -> None:
            """Reconnected to controller."""
            if ctrl is not self._controller:
                return
            self.set_available(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_RECONNECTED, controller_reconnected
            )
        )

        @callback
        def controller_update(ctrl: Controller) -> None:
            """Handle controller data updates."""
            if ctrl is not self._controller:
                return
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCH_CONTROLLER_UPDATE, controller_update
            )
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @callback
    def set_available(self, available: bool, ex: Exception = None) -> None:
        """Set availability for the controller."""
        if self.available == available:
            return

        if available:
            _LOGGER.info("Reconnected controller %s ", self._controller.device_uid)
        else:
            _LOGGER.info(
                "Controller %s disconnected due to exception: %s",
                self._controller.device_uid,
                ex,
            )

        self._available = available
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device info for the Escea system."""
        return self._device_info

    @property
    def unique_id(self):
        """Return the ID of the controller device."""
        return self._controller.device_uid

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Escea Fireplace {self._controller.device_uid}"

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._supported_features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        return {}

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return HVAC_MODE_HEAT if self._controller.is_on else HVAC_MODE_OFF

    @property
    @_return_on_connection_error([])
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_HEAT]

    @property
    @_return_on_connection_error()
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._controller.current_temp

    @property
    @_return_on_connection_error()
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._controller.desired_temp

    @property
    @_return_on_connection_error()
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return _ESCEA_FAN_TO_HA[self._controller.fan]

    @property
    @_return_on_connection_error()
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return list(self._fan_to_pescea)

    @property
    @_return_on_connection_error(4.0)
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._controller.min_temp

    @property
    @_return_on_connection_error(30.0)
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._controller.max_temp

    async def wrap_and_catch(self, coro: Coroutine):
        """Catch any connection errors and set unavailable."""
        try:
            await coro
        except ConnectionError as ex:
            self.set_available(False, ex)
        else:
            self.set_available(True)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.wrap_and_catch(self._controller.set_desired_temp(temp))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan = self._fan_to_pescea[fan_mode]
        await self.wrap_and_catch(self._controller.set_fan(fan))

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.wrap_and_catch(self._controller.set_on(False))
        elif hvac_mode == HVAC_MODE_HEAT:
            await self.wrap_and_catch(self._controller.set_on(True))

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.wrap_and_catch(self._controller.set_on(True))
