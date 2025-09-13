"""Support for Number configuration parameters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvOff import (
    EvOff as SchalterEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvOn import (
    EvOn as SchalterEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvToggleByDuty import (
    EvToggleByDuty as SchalterEvToggleByDuty,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.Status import (
    Status as SchalterStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.params.EState import EState

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Haus-Bus number entity from a config entry."""

    gateway = config_entry.runtime_data.gateway

    async def async_add_number(channel: HausbusEntity) -> None:
        """Add number from Haus-Bus."""
        async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_number, NUMBER_DOMAIN)


class HausbusControl(HausbusEntity, NumberEntity):
    """Representation of a Haus-Bus control."""

    def __init__(self, channel: ABusFeature, device: HausbusDevice) -> None:
        """Set up switch."""
        super().__init__(channel, device)

        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_native_unit_of_measurement = "%"
        self._value: float = 0
        LOGGER.debug("HausBusControl created %s", self._attr_name)

    def set_native_value_internal(self, native_value: float):
        """Sets native value and trigger ha state update."""
        self._value = native_value
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    @property
    def native_value(self) -> float:
        """Returns native value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Sets native value."""
        LOGGER.debug("async_set_native_value value %s", value)
        value = int(value)
        self._channel.toggleByDuty(value, 0)
        self.set_native_value_internal(value)

    def handle_event(self, data: Any) -> None:
        """Handle control events from Haus-Bus."""
        if isinstance(data, SchalterEvToggleByDuty):
            newValue = data.getDuty()
            LOGGER.debug("new value by event %s", newValue)
            self.set_native_value_internal(newValue)
        elif isinstance(data, SchalterEvOn):
            self.set_native_value_internal(100)
        elif isinstance(data, SchalterStatus):
            if data.getState() == EState.ON:
                self.set_native_value_internal(100)
            elif data.getState() == EState.OFF:
                self.set_native_value_internal(0)
            elif data.getState() == EState.TOGGLE:
                newValue = (
                    data.getOnTime() / (data.getOnTime() + data.getOffTime())
                ) * 100
                newValue = min(newValue, 100)

                LOGGER.debug("new value by event %s", newValue)
                self.set_native_value_internal(newValue)
        elif isinstance(data, (SchalterEvOff)):
            self.set_native_value_internal(0)
