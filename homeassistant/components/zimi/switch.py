"""Platform for switch integration."""

from __future__ import annotations

import logging
from typing import Any

from zcc import ControlPoint

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZimiConfigEntry
from .entity import ZimiEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZimiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zimi Switch platform."""

    api: ControlPoint = config_entry.runtime_data

    outlets: list[ZimiSwitch] = [ZimiSwitch(device, api) for device in api.outlets]

    async_add_entities(outlets)


class ZimiSwitch(ZimiEntity, SwitchEntity):
    """Representation of an Zimi Switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:power-socket-au"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""

        _LOGGER.debug(
            "Sending turn_on() for %s in %s", self._device.name, self._device.room
        )

        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""

        _LOGGER.debug(
            "Sending turn_off() for %s in %s", self._device.name, self._device.room
        )

        await self._device.turn_off()
