"""Representation of a Haus-Bus UI button."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a button from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_button(channel: HausbusButton) -> None:
        """Add button entity."""
        async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_button, BUTTON_DOMAIN)


class HausbusButton(ButtonEntity):
    """Representation of a button."""

    def __init__(
        self, unique_id: str, name: str, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Set up button."""
        super().__init__()

        self._attr_has_entity_name = True
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._callback = callback

    async def async_press(self) -> None:
        """Is called if a button is pressed."""
        LOGGER.debug("button pressed %s", self._attr_name)
        try:
            await self._callback()
        except Exception:
            LOGGER.exception(
                "Error executing button %s", self._attr_name
            )