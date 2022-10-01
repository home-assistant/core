"""Support for Supla switch."""
from __future__ import annotations

import logging
from pprint import pformat
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, SUPLA_COORDINATORS, SUPLA_SERVERS, SuplaChannel

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Supla switches."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    entities = []
    for device in discovery_info.values():
        server_name = device["server_name"]

        entities.append(
            SuplaSwitch(
                device,
                hass.data[DOMAIN][SUPLA_SERVERS][server_name],
                hass.data[DOMAIN][SUPLA_COORDINATORS][server_name],
            )
        )

    async_add_entities(entities)


class SuplaSwitch(SuplaChannel, SwitchEntity):
    """Representation of a Supla Switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.async_action("TURN_ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.async_action("TURN_OFF")

    @property
    def is_on(self):
        """Return true if switch is on."""
        if state := self.channel_data.get("state"):
            return state["on"]
        return False
