"""Support for Z-Wave cover devices."""
from __future__ import annotations

import logging
from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import TARGET_STATE_PROPERTY, TARGET_VALUE_PROPERTY
from zwave_js_server.const.command_class.barrier_operator import BarrierState
from zwave_js_server.const.command_class.multilevel_switch import (
    COVER_CLOSE_PROPERTY,
    COVER_DOWN_PROPERTY,
    COVER_OFF_PROPERTY,
    COVER_ON_PROPERTY,
    COVER_OPEN_PROPERTY,
    COVER_UP_PROPERTY,
)
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)


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

    config_entry.async_on_unload(
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

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveCover entity."""
        super().__init__(config_entry, client, info)

        # Entity class attributes
        self._attr_device_class = DEVICE_CLASS_WINDOW
        if self.info.platform_hint == "window_shutter":
            self._attr_device_class = DEVICE_CLASS_SHUTTER
        if self.info.platform_hint == "window_blind":
            self._attr_device_class = DEVICE_CLASS_BLIND

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
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)
        await self.info.node.async_set_value(
            target_value, percent_to_zwave_position(kwargs[ATTR_POSITION])
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)
        await self.info.node.async_set_value(target_value, 99)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)
        await self.info.node.async_set_value(target_value, 0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        open_value = (
            self.get_zwave_value(COVER_OPEN_PROPERTY)
            or self.get_zwave_value(COVER_UP_PROPERTY)
            or self.get_zwave_value(COVER_ON_PROPERTY)
        )
        if open_value:
            # Stop the cover if it's opening
            await self.info.node.async_set_value(open_value, False)

        close_value = (
            self.get_zwave_value(COVER_CLOSE_PROPERTY)
            or self.get_zwave_value(COVER_DOWN_PROPERTY)
            or self.get_zwave_value(COVER_OFF_PROPERTY)
        )
        if close_value:
            # Stop the cover if it's closing
            await self.info.node.async_set_value(close_value, False)


class ZwaveMotorizedBarrier(ZWaveBaseEntity, CoverEntity):
    """Representation of a Z-Wave motorized barrier device."""

    _attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE
    _attr_device_class = DEVICE_CLASS_GARAGE

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZwaveMotorizedBarrier entity."""
        super().__init__(config_entry, client, info)
        self._target_state: ZwaveValue = self.get_zwave_value(
            TARGET_STATE_PROPERTY, add_to_watched_value_ids=False
        )

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value == BarrierState.OPENING)

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value == BarrierState.CLOSING)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self.info.primary_value.value is None:
            return None
        # If a barrier is in the stopped state, the only way to proceed is by
        # issuing an open cover command. Return None in this case which
        # produces an unknown state and allows it to be resolved with an open
        # command.
        if self.info.primary_value.value == BarrierState.STOPPED:
            return None

        return bool(self.info.primary_value.value == BarrierState.CLOSED)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        await self.info.node.async_set_value(self._target_state, BarrierState.OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        await self.info.node.async_set_value(self._target_state, BarrierState.CLOSED)
