"""Support for Z-Wave cover devices."""
from __future__ import annotations

import logging
from typing import Any, Callable

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue, get_value_id

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_GARAGE,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

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

FIBARO_FGR222_CONFIGURATION_REPORTS_TYPE_PROPERTY = 3
FIBARO_FGR222_CONFIGURATION_REPORTS_TYPE_MANUFAC_PROP = 1
FIBARO_FGR222_CONFIGURATION_OPERATING_MODE_PROPERTY = 10
FIBARO_FGR222_CONFIGURATION_OPERATING_MODE_VENETIAN_WITH_POSITION = 2
FIBARO_FGR222_MANUFACTURER_PROPRIETARY_BLINDS_POSITION_PROPERTY = (
    "fibaro-venetianBlindsPosition"
)
FIBARO_FGR222_MANUFACTURER_PROPRIETARY_BLINDS_TILT_PROPERTY = (
    "fibaro-venetianBlindsTilt"
)


def get_node_configuration_value(node: ZwaveNode, property_: int) -> Any | None:
    """Return a node's configuration value, if any."""
    config_values = node.get_configuration_values()

    value_id = get_value_id(
        node,
        CommandClass.CONFIGURATION,
        property_,
        endpoint=0,
    )
    if value_id not in config_values:
        return None

    return config_values[value_id].value


def is_fgr222_in_venetian_config(info: ZwaveDiscoveryInfo) -> bool:
    """Check if node is an FGR222 in sane venetian blinds configuration."""
    if info.platform_hint != "fibaro_fgr222":
        return False

    # Is the node reporting through the "Manufacturer Proprietary" value?
    if (
        get_node_configuration_value(
            info.node, FIBARO_FGR222_CONFIGURATION_REPORTS_TYPE_PROPERTY
        )
        is not FIBARO_FGR222_CONFIGURATION_REPORTS_TYPE_MANUFAC_PROP
    ):
        return False

    # Is the node configured as "venetian blind mode with positioning"?
    if (
        get_node_configuration_value(
            info.node, FIBARO_FGR222_CONFIGURATION_OPERATING_MODE_PROPERTY
        )
        is not FIBARO_FGR222_CONFIGURATION_OPERATING_MODE_VENETIAN_WITH_POSITION
    ):
        return False

    LOGGER.debug("Node %u detected as FGR222 in venetian config", info.node.node_id)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave Cover from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_cover(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave cover."""
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "motorized_barrier":
            entities.append(ZwaveMotorizedBarrier(config_entry, client, info))
        elif is_fgr222_in_venetian_config(info):
            entities.append(FGR222Venetian(config_entry, client, info))
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


def zwave_position_to_percent(value: int) -> int:
    """Convert position in 0-99 scale to 0-100 scale.

    `value` -- (int) Position byte value from 0-99.
    """
    return round((value / 99) * 100)


class ZWaveCover(ZWaveBaseEntity, CoverEntity):
    """Representation of a Z-Wave Cover device."""

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value == 0)

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return zwave_position_to_percent(self.info.primary_value.value)

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


class FGR222Venetian(ZWaveCover):
    """Implementation of the FGR-222 in proprietary venetian configuration.

    This adds support for the tilt feature for the ventian blind mode.

    To enable this, the following node configuration values must be set:
      * Set "3: Reports type to Blind position reports sent"
          to value "the main controller using Fibaro Command Class"
      * Set "10: Roller Shutter operating modes"
          to  value "2 - Venetian Blind Mode, with positioning"
    """

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the FGR-222."""
        super().__init__(config_entry, client, info)

        self._blinds_position = self.get_zwave_value(
            FIBARO_FGR222_MANUFACTURER_PROPRIETARY_BLINDS_POSITION_PROPERTY,
            command_class=CommandClass.MANUFACTURER_PROPRIETARY,
            add_to_watched_value_ids=True,
        )

        self._tilt_position = self.get_zwave_value(
            FIBARO_FGR222_MANUFACTURER_PROPRIETARY_BLINDS_TILT_PROPERTY,
            command_class=CommandClass.MANUFACTURER_PROPRIETARY,
            add_to_watched_value_ids=True,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        pos = self.current_cover_position
        if pos is None:
            return None

        return bool(pos == 0)

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._blinds_position is None:
            return None
        if self._blinds_position.value is None:
            return None

        # On the FGR-222, when it is controlling venetian blinds, it can happen that the cover
        # position can't reach 0 or 99. On top of that, the tilt position can influence the reported
        # cover position as well. That is, fully open or fully closed blinds can shift the blinds
        # position value.
        #
        # Hence, saturate a bit earlier in each direction.
        pos = self._blinds_position.value  # This is a Zwave value, so range is: 0-99
        if pos < 4:
            pos = 0
        if pos > 95:
            pos = 99

        return zwave_position_to_percent(pos)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._tilt_position is None:
            return None
        if self._tilt_position.value is None:
            return None

        return zwave_position_to_percent(self._tilt_position.value)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if self.current_cover_position is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_SET_TILT_POSITION
            )

        return supported_features

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if self._tilt_position:
            await self.info.node.async_set_value(self._tilt_position, 99)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if self._tilt_position:
            await self.info.node.async_set_value(self._tilt_position, 0)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if self._tilt_position:
            await self.info.node.async_set_value(
                self._tilt_position,
                percent_to_zwave_position(kwargs[ATTR_TILT_POSITION]),
            )


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
