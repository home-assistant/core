"""Support for Dyson infrared fans."""

import asyncio
from typing import Any

from infrared_protocols.codes.dyson.cool import DysonCoolStateBuilder

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_EMITTER_ENTITY_ID

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Dyson infrared fan platform from a config entry."""
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    async_add_entities(
        [DysonInfraredFan(infrared_emitter_entity_id, entry.entry_id, entry.title)]
    )


class DysonInfraredFan(InfraredEmitterConsumerEntity, FanEntity):
    """Representation of a Dyson infrared fan entity."""

    def __init__(
        self, infrared_emitter_entity_id: str, unique_id: str, name: str
    ) -> None:
        """Initialize the Dyson infrared fan entity."""
        self._infrared_emitter_entity_id = infrared_emitter_entity_id

        self._attr_translation_key = "dyson_ir_fan"
        self._attr_unique_id = unique_id
        self._attr_has_entity_name = True
        self._attr_speed_count = 10
        self._attr_percentage = 50
        self._attr_is_on = False
        self._attr_assumed_state = True

        self._attr_supported_features = (
            FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
        )

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self._attr_is_on or False

    async def _async_send_dyson_action(self, action: str) -> None:
        builder = DysonCoolStateBuilder(action=action)
        command = builder.to_command()
        await self._send_command(command)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_send_dyson_action("on")
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_send_dyson_action("off")
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
        current_percentage = self._attr_percentage or 0
        if percentage == current_percentage:
            return
        step_size = 100 / self._attr_speed_count
        steps = round(abs(percentage - current_percentage) / step_size)
        action = "speed_up" if percentage > current_percentage else "speed_down"
        for _ in range(steps):
            await self._async_send_dyson_action(action)
            await asyncio.sleep(0.2)

        self._attr_percentage = percentage
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation state of the fan."""
        await self._async_send_dyson_action("swing")
        self._attr_oscillating = oscillating
        self.async_write_ha_state()
