"""Support for TPLink HS100/HS110/HS200 smart switch."""
from __future__ import annotations

from asyncio import sleep

import logging
from typing import Any

from kasa import SmartDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.tplink import TPLinkDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import CoordinatedTPLinkEntity
from .const import CONF_SWITCH, COORDINATORS, DOMAIN as TPLINK_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    entities: list[SmartPlugSwitch] = []
    coordinators: dict[str, TPLinkDataUpdateCoordinator] = hass.data[TPLINK_DOMAIN][
        COORDINATORS
    ]
    switches: list[SmartDevice] = hass.data[TPLINK_DOMAIN][CONF_SWITCH]
    for switch in switches:
        coordinator = coordinators[switch.device_id]
        entities.append(SmartPlugSwitch(switch, coordinator))
        if switch.is_strip:
            _LOGGER.info("initializing strip with %s sockets", len(switch.children))
            for child in switch.children:
                entities.append(SmartPlugSwitch(child, coordinator))

    async_add_entities(entities)


class SmartPlugSwitch(CoordinatedTPLinkEntity, SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.device.turn_on()
        # Workaround for delayed device state update on HS210: #55190
        if "HS210" in self.device.model:
            await sleep(0.5)

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.device.turn_off()
        # Workaround for delayed device state update on HS210: #55190
        if "HS210" in self.device.model:
            await sleep(0.5)

        await self.coordinator.async_refresh()
