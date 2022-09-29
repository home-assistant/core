"""Support for Supla cover - curtains, rollershutters, entry gate etc."""
from __future__ import annotations

import logging
from pprint import pformat
from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverDeviceClass, CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, SUPLA_COORDINATORS, SUPLA_SERVERS, SuplaChannel

_LOGGER = logging.getLogger(__name__)

SUPLA_SHUTTER = "CONTROLLINGTHEROLLERSHUTTER"
SUPLA_GATE = "CONTROLLINGTHEGATE"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Supla covers."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    entities: list[CoverEntity] = []
    for device in discovery_info.values():
        device_name = device["function_name"]
        server_name = device["server_name"]

        if device_name == SUPLA_SHUTTER:
            entities.append(
                SuplaCover(
                    device,
                    hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                    hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
                )
            )

        elif device_name == SUPLA_GATE:
            entities.append(
                SuplaGateDoor(
                    device,
                    hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                    hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
                )
            )

    async_add_entities(entities)


class SuplaCover(SuplaChannel, CoverEntity):
    """Representation of a Supla Cover."""

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover. 0 is closed, 100 is open."""
        if state := self.channel_data.get("state"):
            return 100 - state["shut"]
        return None

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.async_action("REVEAL", percentage=kwargs.get(ATTR_POSITION))

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        return self.current_cover_position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.async_action("REVEAL")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.async_action("SHUT")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.async_action("STOP")


class SuplaGateDoor(SuplaChannel, CoverEntity):
    """Representation of a Supla gate door."""

    @property
    def is_closed(self) -> bool | None:
        """Return if the gate is closed or not."""
        state = self.channel_data.get("state")
        if state and "hi" in state:
            return state.get("hi")
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the gate."""
        if self.is_closed:
            await self.async_action("OPEN_CLOSE")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the gate."""
        if not self.is_closed:
            await self.async_action("OPEN_CLOSE")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the gate."""
        await self.async_action("OPEN_CLOSE")

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the gate."""
        await self.async_action("OPEN_CLOSE")

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return CoverDeviceClass.GARAGE
