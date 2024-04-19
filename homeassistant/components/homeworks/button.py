"""Support for Lutron Homeworks buttons."""

from __future__ import annotations

import asyncio

from pyhomeworks.pyhomeworks import Homeworks

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeworksData, HomeworksEntity
from .const import (
    CONF_ADDR,
    CONF_BUTTONS,
    CONF_CONTROLLER_ID,
    CONF_KEYPADS,
    CONF_NUMBER,
    CONF_RELEASE_DELAY,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Homeworks buttons."""
    data: HomeworksData = hass.data[DOMAIN][entry.entry_id]
    controller = data.controller
    controller_id = entry.options[CONF_CONTROLLER_ID]
    entities = []
    for keypad in entry.options.get(CONF_KEYPADS, []):
        for button in keypad[CONF_BUTTONS]:
            entity = HomeworksButton(
                controller,
                controller_id,
                keypad[CONF_ADDR],
                keypad[CONF_NAME],
                button[CONF_NAME],
                button[CONF_NUMBER],
                button[CONF_RELEASE_DELAY],
            )
            entities.append(entity)
    async_add_entities(entities, True)


class HomeworksButton(HomeworksEntity, ButtonEntity):
    """Homeworks Button."""

    def __init__(
        self,
        controller: Homeworks,
        controller_id: str,
        addr: str,
        keypad_name: str,
        button_name: str,
        button_number: int,
        release_delay: float,
    ) -> None:
        """Create device with Addr, name, and rate."""
        super().__init__(controller, controller_id, addr, button_number, button_name)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{controller_id}.{addr}")}, name=keypad_name
        )
        self._release_delay = release_delay

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(
            # pylint: disable-next=protected-access
            self._controller._send,
            f"KBP, {self._addr}, {self._idx}",
        )
        if not self._release_delay:
            return
        await asyncio.sleep(self._release_delay)
        # pylint: disable-next=protected-access
        await self.hass.async_add_executor_job(
            # pylint: disable-next=protected-access
            self._controller._send,
            f"KBR, {self._addr}, {self._idx}",
        )
