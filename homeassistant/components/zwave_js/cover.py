"""Support for Z-Wave cover devices."""
from __future__ import annotations

import logging
from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_GARAGE,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import AddEntitiesCallback

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)

BARRIER_TARGET_CLOSE = 0
BARRIER_TARGET_OPEN = 255

BARRIER_STATE_CLOSED = 0
BARRIER_STATE_CLOSING = 252
BARRIER_STATE_STOPPED = 253
BARRIER_STATE_OPENING = 254
BARRIER_STATE_OPEN = 255


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Cover from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_cover(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave cover."""
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "motorized_barrier":
            entities.append(ZwaveMotorizedBarrier(config_entry, client, info))
        else:
            entities.append(ZWaveCover(config_entry, client, info))
        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{COVER_DOMAIN}",
            async_add_cover,
        )
    )


def percent_to_zwave_position(value: int) -> int:
    """Convert position in 0-100 scale to 0-99 scale.

    `value` -- (int) Position byte value from 0-100.
    """
    if value > 0:
        return max(1, round((value / 100) * 99))
    return 0


class ZWaveCover(ZWaveBaseEntity, CoverEntity):
    """Representation of a Z-Wave Cover device."""

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value == 0)

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of cover where 0 means closed and 100 is fully open."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return round((self.info.primary_value.value / 99) * 100)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(
            target_value, percent_to_zwave_position(kwargs[ATTR_POSITION])
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, 99)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, 0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        target_value = self.get_zwave_value("Open") or self.get_zwave_value("Up")
        if target_value:
            await self.info.node.async_set_value(target_value, False)
        target_value = self.get_zwave_value("Close") or self.get_zwave_value("Down")
        if target_value:
            await self.info.node.async_set_value(target_value, False)


class ZwaveMotorizedBarrier(ZWaveBaseEntity, CoverEntity):
    """Representation of a Z-Wave motorized barrier device."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZwaveMotorizedBarrier entity."""
        super().__init__(config_entry, client, info)
        self._target_state: ZwaveValue = self.get_zwave_value(
            "targetState", add_to_watched_value_ids=False
        )

    @property
    def supported_features(self) -> int | None:
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value == BARRIER_STATE_OPENING)

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value == BARRIER_STATE_CLOSING)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self.info.primary_value.value is None:
            return None
        # If a barrier is in the stopped state, the only way to proceed is by
        # issuing an open cover command. Return None in this case which
        # produces an unknown state and allows it to be resolved with an open
        # command.
        if self.info.primary_value.value == BARRIER_STATE_STOPPED:
            return None

        return bool(self.info.primary_value.value == BARRIER_STATE_CLOSED)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        await self.info.node.async_set_value(self._target_state, BARRIER_TARGET_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        await self.info.node.async_set_value(self._target_state, BARRIER_TARGET_CLOSE)
