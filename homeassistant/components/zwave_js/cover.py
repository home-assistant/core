"""Support for Z-Wave cover devices."""
import logging
from typing import Callable, List

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)
SUPPORT_GARAGE = SUPPORT_OPEN | SUPPORT_CLOSE


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave Light from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_cover(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave cover."""
        entities: List[ZWaveBaseEntity] = []

        if info.platform_hint == "garage_cover":
            entities.append(ZWaveGarageDoorBarrier(client, info))
        elif info.platform_hint == "cover":
            entities.append(ZWaveCover(client, info))
        else:
            LOGGER.warning(
                "Sensor not implemented for %s/%s",
                info.platform_hint,
                info.primary_value.propertyname,
            )
            return
        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_{COVER_DOMAIN}", async_add_cover)
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
    def is_closed(self) -> bool:
        """Return true if cover is closed."""
        if self.info.primary_value.value > 0:
            return False
        return True

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover where 0 means closed and 100 is fully open."""
        return round((self.info.primary_value.value / 99) * 100)

    # TODO: update these functions once upstream PR for barriers is completed
    # async def async_set_cover_position(self, **kwargs):
    #     """Move the cover to a specific position."""
    #     await self.info.node.async_set_value(percent_to_zwave_position(kwargs[ATTR_POSITION]))

    # async def async_open_cover(self, **kwargs):
    #     """Open the cover."""
    #     self.values.open.send_value(PRESS_BUTTON)

    # async def async_close_cover(self, **kwargs):
    #     """Close cover."""
    #     self.values.close.send_value(PRESS_BUTTON)

    # async def async_stop_cover(self, **kwargs):
    #     """Stop cover."""
    #     # Need to issue both buttons release since qt-openzwave implements idempotency
    #     # keeping internal state of model to trigger actual updates. We could also keep
    #     # another state in Home Assistant to know which button to release,
    #     # but this implementation is simpler.
    #     self.values.open.send_value(RELEASE_BUTTON)
    #     self.values.close.send_value(RELEASE_BUTTON)


class ZWaveGarageDoorBarrier(ZWaveBaseEntity, CoverEntity):
    """Representation of a barrier operator Zwave garage door device."""

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_GARAGE

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def is_opening(self) -> bool:
        """Return true if cover is in an opening state."""
        if self.info.primary_value.value == 3:
            return True
        return False

    @property
    def is_closing(self) -> bool:
        """Return true if cover is in a closing state."""
        if self.info.primary_value.value == 1:
            return True
        return False

    @property
    def is_closed(self) -> bool:
        """Return the current position of Zwave garage door."""
        if self.info.primary_value.value == 0:
            return True
        return False

    # TODO: update these functions once upstream PR for barriers is completed
    # async def async_close_cover(self, **kwargs: int) -> None:
    #     """Close the garage door."""
    #     await self.info.node.async_set_value(0)

    # async def async_open_cover(self, **kwargs: int) -> None:
    #     """Open the garage door."""
    #     await self.info.node.async_set_value(4)
