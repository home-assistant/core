"""Support for the Escea HVAC."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging

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
    ICON,
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
        conf = hass.data.get(DATA_CONFIG)

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


class ControllerDevice(ClimateEntity):
    """Representation of Escea Controller."""

    _attr_hvac_modes = [
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = TEMP_CELSIUS

    _attr_precision = PRECISION_WHOLE
    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(self, controller: Controller) -> None:
        """Initialise ControllerDevice."""
        self._controller = controller

        self._attr_min_temp = controller.min_temp
        self._attr_max_temp = controller.max_temp

        self._fan_to_pescea = {}
        for fan in controller.Fan:
            self._fan_to_pescea[_ESCEA_FAN_TO_HA[fan]] = fan
        self._attr_fan_modes = list(self._fan_to_pescea)

        self._attr_unique_id = controller.device_uid
        self._attr_name = f"Escea Fireplace {self._attr_unique_id}"

        self._attr_available = True

    async def async_added_to_hass(self):
        """Call on adding to hass.

        Registers for connect/disconnect/update events
        """

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

    @callback
    def set_available(self, available: bool, ex: Exception = None) -> None:
        """Set availability for the controller."""
        if self._attr_available == available:
            return

        if available:
            _LOGGER.info("Reconnected controller %s ", self._controller.device_uid)
        else:
            _LOGGER.info(
                "Controller %s disconnected due to exception: %s",
                self._controller.device_uid,
                ex,
            )

        self._attr_available = available
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device info for the Escea system."""
        return {
            "identifiers": {(ESCEA, self.unique_id)},
            "name": self.name,
            "manufacturer": "Escea",
        }

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return HVAC_MODE_HEAT if self._controller.is_on else HVAC_MODE_OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._controller.current_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._controller.desired_temp

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return _ESCEA_FAN_TO_HA[self._controller.fan]

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
