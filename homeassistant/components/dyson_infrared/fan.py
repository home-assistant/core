from __future__ import annotations

from typing import Any

from infrared_protocols.codes.dyson.cool import DysonCoolStateBuilder

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_EMITTER_ENTITY_ID


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    async_add_entities(
        [DysonInfraredFan(infrared_emitter_entity_id, entry.entry_id, entry.title)]
    )


class DysonInfraredFan(InfraredEmitterConsumerEntity, FanEntity):
    def __init__(
        self, infrared_emitter_entity_id: str, unique_id: str, name: str
    ) -> None:
        self._infrared_emitter_entity_id = infrared_emitter_entity_id

        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_speed_count = 10
        self._attr_percentage = 50
        self._attr_supported_features = (
            FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
        )

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
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_send_dyson_action("on")
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_send_dyson_action("off")
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return

        current_percentage = self._attr_percentage or 0

        if percentage > current_percentage:
            await self._async_send_dyson_action("speed_up")
        elif percentage < current_percentage:
            await self._async_send_dyson_action("speed_down")

        self._attr_percentage = percentage
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._async_send_dyson_action("swing")
        self._attr_oscillating = oscillating
        self.async_write_ha_state()
