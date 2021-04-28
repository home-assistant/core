"""Support for Z-Wave fans."""
from __future__ import annotations

import math
from typing import Any

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

SPEED_RANGE = (1, 99)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Fan from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_fan(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave fan."""
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZwaveFan(config_entry, client, info))
        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{FAN_DOMAIN}",
            async_add_fan,
        )
    )


class ZwaveFan(ZWaveBaseEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    async def async_set_percentage(self, percentage: int | None) -> None:
        """Set the speed percentage of the fan."""
        target_value = self.get_zwave_value("targetValue")

        if percentage is None:
            # Value 255 tells device to return to previous value
            zwave_speed = 255
        elif percentage == 0:
            zwave_speed = 0
        else:
            zwave_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        await self.info.node.async_set_value(target_value, zwave_speed)

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, 0)

    @property
    def is_on(self) -> bool | None:  # type: ignore
        """Return true if device is on (speed above 0)."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value > 0)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self.info.primary_value.value)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES
