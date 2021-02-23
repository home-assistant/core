"""Support for Tasmota fans."""

from typing import Optional

from hatasmota import const as tasmota_const

from homeassistant.components import fan
from homeassistant.components.fan import FanEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

ORDERED_NAMED_FAN_SPEEDS = [
    tasmota_const.FAN_SPEED_LOW,
    tasmota_const.FAN_SPEED_MEDIUM,
    tasmota_const.FAN_SPEED_HIGH,
]  # off is not included


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota fan dynamically through discovery."""

    @callback
    def async_discover(tasmota_entity, discovery_hash):
        """Discover and add a Tasmota fan."""
        async_add_entities(
            [TasmotaFan(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(fan.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(fan.DOMAIN),
        async_discover,
    )


class TasmotaFan(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    FanEntity,
):
    """Representation of a Tasmota fan."""

    def __init__(self, **kwds):
        """Initialize the Tasmota fan."""
        self._state = None

        super().__init__(
            **kwds,
        )

    @property
    def speed_count(self) -> Optional[int]:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self):
        """Return the current speed percentage."""
        if self._state is None:
            return None
        if self._state == 0:
            return 0
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, self._state)

    @property
    def supported_features(self):
        """Flag supported features."""
        return fan.SUPPORT_SET_SPEED

    async def async_set_percentage(self, percentage):
        """Set the speed of the fan."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            tasmota_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )
            self._tasmota_entity.set_speed(tasmota_speed)

    async def async_turn_on(
        self, speed=None, percentage=None, preset_mode=None, **kwargs
    ):
        """Turn the fan on."""
        # Tasmota does not support turning a fan on with implicit speed
        await self.async_set_percentage(
            percentage
            or ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, tasmota_const.FAN_SPEED_MEDIUM
            )
        )

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        self._tasmota_entity.set_speed(tasmota_const.FAN_SPEED_OFF)
