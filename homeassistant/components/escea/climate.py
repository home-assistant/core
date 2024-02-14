"""Support for the Escea Fireplace."""
from __future__ import annotations

from collections.abc import Coroutine
import logging
from typing import Any

from pescea import Controller

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_DISCOVERY_SERVICE,
    DISPATCH_CONTROLLER_DISCONNECTED,
    DISPATCH_CONTROLLER_DISCOVERED,
    DISPATCH_CONTROLLER_RECONNECTED,
    DISPATCH_CONTROLLER_UPDATE,
    DOMAIN,
    ESCEA_FIREPLACE,
    ESCEA_MANUFACTURER,
    ICON,
)

_LOGGER = logging.getLogger(__name__)

_ESCEA_FAN_TO_HA = {
    Controller.Fan.FLAME_EFFECT: FAN_LOW,
    Controller.Fan.FAN_BOOST: FAN_HIGH,
    Controller.Fan.AUTO: FAN_AUTO,
}
_HA_FAN_TO_ESCEA = {v: k for k, v in _ESCEA_FAN_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize an Escea Controller."""
    discovery_service = hass.data[DATA_DISCOVERY_SERVICE]

    @callback
    def init_controller(ctrl: Controller) -> None:
        """Register the controller device."""

        _LOGGER.debug("Controller UID=%s discovered", ctrl.device_uid)

        entity = ControllerEntity(ctrl)
        async_add_entities([entity])

    # create any components not yet created
    for controller in discovery_service.controllers.values():
        init_controller(controller)

    # connect to register any further components
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_CONTROLLER_DISCOVERED, init_controller)
    )


class ControllerEntity(ClimateEntity):
    """Representation of Escea Controller."""

    _attr_fan_modes = list(_HA_FAN_TO_ESCEA)
    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_icon = ICON
    _attr_precision = PRECISION_WHOLE
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, controller: Controller) -> None:
        """Initialise ControllerDevice."""
        self._controller = controller

        self._attr_min_temp = controller.min_temp
        self._attr_max_temp = controller.max_temp

        self._attr_unique_id = controller.device_uid

        # temporary assignment to get past mypy checker
        unique_id: str = controller.device_uid

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=ESCEA_MANUFACTURER,
            name=ESCEA_FIREPLACE,
        )

        self._attr_available = True

    async def async_added_to_hass(self) -> None:
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
    def set_available(self, available: bool, ex: Exception | None = None) -> None:
        """Set availability for the controller."""
        if self._attr_available == available:
            return

        if available:
            _LOGGER.debug("Reconnected controller %s ", self._controller.device_uid)
        else:
            _LOGGER.debug(
                "Controller %s disconnected due to exception: %s",
                self._controller.device_uid,
                ex,
            )

        self._attr_available = available
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        return HVACMode.HEAT if self._controller.is_on else HVACMode.OFF

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

    async def wrap_and_catch(self, coro: Coroutine) -> None:
        """Catch any connection errors and set unavailable."""
        try:
            await coro
        except ConnectionError as ex:
            self.set_available(False, ex)
        else:
            self.set_available(True)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.wrap_and_catch(self._controller.set_desired_temp(temp))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self.wrap_and_catch(self._controller.set_fan(_HA_FAN_TO_ESCEA[fan_mode]))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.wrap_and_catch(self._controller.set_on(hvac_mode == HVACMode.HEAT))

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.wrap_and_catch(self._controller.set_on(True))

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.wrap_and_catch(self._controller.set_on(False))
