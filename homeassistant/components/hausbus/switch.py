"""Support for Haus-Bus switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from pyhausbus.de.hausbus.homeassistant.proxy.Schalter import Schalter
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.Configuration import (
    Configuration as SchalterConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvOff import (
    EvOff as SchalterEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvOn import (
    EvOn as SchalterEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.Status import (
    Status as SchalterStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.params.EState import EState

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus switch from a config entry."""
    gateway = config_entry.runtime_data.gateway

    # Services gelten für alle Hausbus-Entities, die die jeweilige Funktion implementieren
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "switch_off",
        {
            vol.Required("offDelay", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
        },
        "async_switch_off",
    )

    platform.async_register_entity_service(
        "switch_on",
        {
            vol.Required("duration", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
            vol.Optional("onDelay", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=65535)
            ),
        },
        "async_switch_on",
    )

    platform.async_register_entity_service(
        "switch_toggle",
        {
            vol.Required("offTime", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("onTime", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Optional("quantity", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        "async_switch_toggle",
    )

    platform.async_register_entity_service(
        "switch_set_configuration",
        {
            vol.Required("max_on_time", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
            vol.Required("off_delay_time", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
            vol.Required("time_base", default=1000): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        },
        "async_switch_set_configuration",
    )

    async def async_add_switch(channel: HausbusEntity) -> None:
        """Add switch from Haus-Bus."""
        if isinstance(channel, HausbusSwitch):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_switch, SWITCH_DOMAIN)


class HausbusSwitch(HausbusEntity, SwitchEntity):
    """Representation of a Haus-Bus switch."""

    def __init__(self, channel: Schalter, device: HausbusDevice) -> None:
        """Set up switch."""
        super().__init__(channel, device)

        self._attr_is_on = False

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.off(0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        self._channel.on(0, 0)

    def switch_turn_on(self) -> None:
        """Turn off a switch channel."""
        params = {ATTR_ON_STATE: True}
        self.async_update_callback(**params)

    def switch_turn_off(self) -> None:
        """Turn off a switch channel."""
        params = {ATTR_ON_STATE: False}
        self.async_update_callback(**params)

    def handle_event(self, data: Any) -> None:
        """Handle switch events from Haus-Bus."""
        if isinstance(data, SchalterEvOn):
            self.switch_turn_on()
        elif isinstance(data, SchalterStatus):
            if data.getState() == EState.ON:
                self.switch_turn_on()
            else:
                self.switch_turn_off()
        elif isinstance(data, (SchalterEvOff)):
            self.switch_turn_off()
        elif isinstance(data, SchalterConfiguration):
            self._configuration = data
            self._attr_extra_state_attributes["max_on_time"] = data.getMaxOnTime()
            self._attr_extra_state_attributes["off_delay_time"] = data.getOffDelayTime()
            self._attr_extra_state_attributes["time_base"] = data.getTimeBase()
            LOGGER.debug(
                f"_attr_extra_state_attributes {self._attr_extra_state_attributes}"
            )

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Switch state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs and self._attr_is_on != kwargs[ATTR_ON_STATE]:
            self._attr_is_on = kwargs[ATTR_ON_STATE]
            state_changed = True

        if state_changed:
            self.schedule_update_ha_state()

    @callback
    async def async_switch_off(self, offDelay: int):
        """Switches a relay with the given off delay time"""
        LOGGER.debug("async_switch_off offDelay %s", offDelay)
        self._channel.off(offDelay)

    @callback
    async def async_switch_on(self, duration: int, onDelay: int):
        """Switches a relay for given duration and on delay time"""
        LOGGER.debug("async_switch_on duration %s, onDelay %s", duration, onDelay)
        self._channel.on(duration, onDelay)

    @callback
    async def async_switch_toggle(self, offTime: int, onTime: int, quantity: int):
        """Toggels a relay with interval with given off and on time and quantity"""
        LOGGER.debug(
            f"async_switch_toggle offTime {offTime}, onTime {onTime}, quantity {quantity}"
        )
        self._channel.toggle(offTime, onTime, quantity)

    @callback
    async def async_switch_set_configuration(
        self, max_on_time: int, off_delay_time: int, time_base: int
    ):
        """Setzt die Konfiguration eines Relais."""
        LOGGER.debug(
            f"async_switch_set_configuration max_on_time {max_on_time}, off_delay_time {off_delay_time}, time_base {time_base}"
        )
        if not self._configuration:
            LOGGER.debug("reading missing configuration")
            self._channel.getConfiguration()
            raise HomeAssistantError(
                "Configuration needed update. Please repeat configuration"
            )
        self._channel.setConfiguration(
            max_on_time,
            off_delay_time,
            time_base,
            self._configuration.getOptions(),
            self._configuration.getDisableBitIndex(),
        )
        self._channel.getConfiguration()
