"""Support for Dyson infrared fans."""

import asyncio
from typing import Any, override

from infrared_protocols.codes.dyson.cool import DysonCoolCode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN

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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

        self._attr_supported_features = (
            FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self._attr_is_on or False

    async def _async_send_dyson_action(self, code: DysonCoolCode) -> None:
        command = code.to_command()
        await self._send_command(command)

    def _percentage_to_speed(self, percentage: int) -> int:
        """Convert a percentage into a discrete speed level (1..speed_count)."""
        step_size = 100 / self._attr_speed_count
        return max(1, min(self._attr_speed_count, round(percentage / step_size)))

    def _speed_to_percentage(self, speed: int) -> int:
        """Convert a discrete speed level back to its normalized percentage."""
        step_size = 100 / self._attr_speed_count
        return round(speed * step_size)

    @override
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
        await self._async_send_dyson_action(DysonCoolCode.ON)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._async_send_dyson_action(DysonCoolCode.OFF)
        self._attr_is_on = False
        self.async_write_ha_state()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        target_speed = self._percentage_to_speed(percentage)
        normalized_percentage = self._speed_to_percentage(target_speed)
        current_speed = self._percentage_to_speed(self._attr_percentage or 0)

        if target_speed == current_speed and self._attr_is_on:
            return

        if target_speed == current_speed:
            # Fan is off but already at the requested speed level: just turn it on.
            await self._async_send_dyson_action(DysonCoolCode.ON)
        else:
            code = (
                DysonCoolCode.SPEED_UP
                if target_speed > current_speed
                else DysonCoolCode.SPEED_DOWN
            )
            for _ in range(abs(target_speed - current_speed)):
                await self._async_send_dyson_action(code)
                await asyncio.sleep(0.2)

        self._attr_percentage = normalized_percentage
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the oscillation state of the fan."""
        await self._async_send_dyson_action(DysonCoolCode.SWING)
        self._attr_oscillating = oscillating
        self.async_write_ha_state()
