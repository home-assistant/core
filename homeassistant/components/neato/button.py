"""Support for Neato buttons."""
from __future__ import annotations

import logging

from pybotvac import Robot

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_DOMAIN, NEATO_ROBOTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato button from config entry."""
    entities = [
        NeatoDismissAlertButton(robot)
        for robot in hass.data[NEATO_ROBOTS]
    ]

    _LOGGER.debug("Adding vacuum buttons %s", entities)
    async_add_entities(entities, True)


class NeatoDismissAlertButton(ButtonEntity):
    """Representation of a dismiss_alert button entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        robot: Robot,
    ) -> None:
        """Initialize a dismiss_alert Neato button entity."""
        self.robot = robot
        self._attr_name = f"{robot.name} Dismiss Alert"
        self._attr_unique_id = f"{robot.serial}_dismiss_alert"
        self._attr_device_info = DeviceInfo(
            identifiers={(NEATO_DOMAIN, robot.serial)}
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(self.robot.dismiss_current_alert)
