"""Fan platform for the Ceiling Fan Infrared integration."""

import math
from typing import Any, override

from infrared_protocols.codes.generic.ceiling_fan import GenericCeilingFanCode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import CONF_INFRARED_ENTITY_ID
from .entity import CeilingFanIrBaseEntity

PARALLEL_UPDATES = 1

SPEED_COUNT = 3
SPEED_RANGE = (1, SPEED_COUNT)
SPEED_CODES = {
    1: GenericCeilingFanCode.FAN_LOW,
    2: GenericCeilingFanCode.FAN_MEDIUM,
    3: GenericCeilingFanCode.FAN_HIGH,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan platform from a config entry."""
    async_add_entities(
        [CeilingFanIrFanEntity(entry, entry.data[CONF_INFRARED_ENTITY_ID])]
    )


class CeilingFanIrFanEntity(
    CeilingFanIrBaseEntity, InfraredEmitterConsumerEntity, FanEntity
):
    """Represents a ceiling fan controlled through an infrared emitter.

    The remote has a single key to toggle the fan on and off and dedicated keys
    for the three speeds, so the speed is known but the on and off state is
    assumed.
    """

    _attr_assumed_state = True
    _attr_name = None
    _attr_speed_count = SPEED_COUNT
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_unique_id = entry.entry_id

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self._attr_is_on or False

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on, optionally at a given speed."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._send_command(GenericCeilingFanCode.FAN_TOGGLE.to_command())
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._send_command(GenericCeilingFanCode.FAN_TOGGLE.to_command())
        self._attr_is_on = False
        self._attr_percentage = 0
        self.async_write_ha_state()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        speed = max(1, min(SPEED_COUNT, speed))
        await self._send_command(SPEED_CODES[speed].to_command())
        self._attr_percentage = ranged_value_to_percentage(SPEED_RANGE, speed)
        self._attr_is_on = True
        self.async_write_ha_state()
