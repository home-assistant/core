"""Support for Tasmota fans."""

from __future__ import annotations

from typing import Any

from hatasmota import const as tasmota_const, fan as tasmota_fan
from hatasmota.entity import TasmotaEntity as HATasmotaEntity
from hatasmota.models import DiscoveryHashType

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .entity import TasmotaAvailability, TasmotaDiscoveryUpdate

ORDERED_NAMED_FAN_SPEEDS = [
    tasmota_const.FAN_SPEED_LOW,
    tasmota_const.FAN_SPEED_MEDIUM,
    tasmota_const.FAN_SPEED_HIGH,
]  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tasmota fan dynamically through discovery."""

    @callback
    def async_discover(
        tasmota_entity: HATasmotaEntity, discovery_hash: DiscoveryHashType
    ) -> None:
        """Discover and add a Tasmota fan."""
        async_add_entities(
            [TasmotaFan(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[DATA_REMOVE_DISCOVER_COMPONENT.format(FAN_DOMAIN)] = (
        async_dispatcher_connect(
            hass,
            TASMOTA_DISCOVERY_ENTITY_NEW.format(FAN_DOMAIN),
            async_discover,
        )
    )


class TasmotaFan(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    FanEntity,
):
    """Representation of a Tasmota fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _fan_speed = tasmota_const.FAN_SPEED_MEDIUM
    _tasmota_entity: tasmota_fan.TasmotaFan

    def __init__(self, **kwds: Any) -> None:
        """Initialize the Tasmota fan."""
        self._state: int | None = None

        super().__init__(
            **kwds,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        self._tasmota_entity.set_on_state_callback(self.fan_state_updated)
        await super().async_added_to_hass()

    @callback
    def fan_state_updated(self, state: int, **kwargs: Any) -> None:
        """Handle state updates."""
        self._state = state
        if self._state is not None and self._state != 0:
            # Store the last known fan speed
            self._fan_speed = state
        self.async_write_ha_state()

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._state is None:
            return None
        if self._state == 0:
            return 0
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, self._state)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            tasmota_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )
            await self._tasmota_entity.set_speed(tasmota_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        # Tasmota does not support turning a fan on with implicit speed
        await self.async_set_percentage(
            percentage
            or ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, self._fan_speed
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._tasmota_entity.set_speed(tasmota_const.FAN_SPEED_OFF)
